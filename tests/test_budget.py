from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from mira import branching, research_tree as tree
from mira.budget import measure
from mira.clients import HTTPModel, CallError
from mira.decisions import ScriptedLLM, request
from mira.format import Unit, dumps, loads
from mira.prompts import SLOTS
from mira.research import Research
from mira.interactions import read_records
from mira.inspection import Inspector
from mira.experiments import Experiments
from test_gardener import seed


class CountedModel(ScriptedLLM):
    """Explicit token-count fixture, independent of request byte length."""
    context_window = 16384

    def __init__(self, responses=(), prompt_tokens=100):
        super().__init__(responses)
        self.prompt_tokens = prompt_tokens

    def count_tokens(self, serialized):
        return {"prompt_tokens": self.prompt_tokens, "context_window": self.context_window,
                "estimator": "fixture model tokens"}


class BudgetTests(unittest.TestCase):
    def test_native_tokenizer_counts_formatted_messages_with_special_tokens_and_caches(self):
        model = HTTPModel("http://localhost:8090/v1", "test-model", api_key="private-key", no_thinking=True)
        wire = request(model.model, model.settings, "R1", dict.fromkeys(SLOTS["R1"], None))
        captured = []
        class Opener:
            def open(self, req, timeout):
                captured.append(req)
                if req.full_url.endswith('/props'):
                    result = {"model_alias":"test-model", "default_generation_settings":{"n_ctx":16384}, "chat_template":"fixture"}
                elif req.full_url.endswith('/apply-template'):
                    self_payload = loads(req.data.decode())
                    assert self_payload == loads(wire)
                    assert self_payload['chat_template_kwargs'] == {'enable_thinking':False}
                    result = {"prompt":"<start>fixture 温度<assistant>"}
                else:
                    assert loads(req.data.decode()) == {"content":"<start>fixture 温度<assistant>", "add_special":True, "parse_special":True}
                    result = {"tokens":[1,2,3,4,5]}
                return BytesIO(dumps(result).encode())
        with patch('mira.clients.build_opener', return_value=Opener()):
            usage = model.count_tokens(wire)
            self.assertEqual(model.count_tokens(wire), usage)
        self.assertEqual(len(captured), 3)
        self.assertEqual(usage['prompt_tokens'], 5)
        self.assertEqual(usage['context_window'], 16384)
        self.assertTrue(all(r.headers['Authorization']=='Bearer private-key' for r in captured))
        self.assertTrue(all(b'private-key' not in (r.data or b'') for r in captured))
        self.assertEqual(measure(wire, 20, 20000, lambda _:usage)['context_budget'], 16384)

    def test_tokenizer_failure_is_explicit_without_byte_fallback(self):
        model = HTTPModel('http://localhost', 'model')
        class Opener:
            def open(self, req, timeout): raise HTTPError(req.full_url, 503, 'offline', {}, BytesIO(b'unavailable'))
        with patch('mira.clients.build_opener', return_value=Opener()):
            with self.assertRaises(CallError): measure('{}', 2048, 16384, model.count_tokens)
        self.assertIn('fallback', measure('{}', 2048, 16384)['estimator'])

    def test_model_identity_and_tokenizer_response_are_checked(self):
        model = HTTPModel('http://localhost', 'model')
        with patch.object(model, '_json', return_value={'model_alias':'other', 'default_generation_settings':{'n_ctx':16384}}):
            self.assertRaisesRegex(ValueError, 'does not match', lambda:model.context_window)
        model = HTTPModel('http://localhost', 'model')
        with patch.object(model, '_json', side_effect=[{'model_alias':'model', 'chat_template':'t', 'default_generation_settings':{'n_ctx':16384}}, {'prompt':'p'}, {'tokens':'invalid'}]):
            self.assertRaisesRegex(ValueError, 'tokenizer response', model.count_tokens, dumps({'model':'model'}))

    def test_exact_exhaustion_boundaries_and_pending_input_deferral(self):
        with tempfile.TemporaryDirectory() as directory:
            model = CountedModel([{'questions':[]}])
            r = Research(directory, model, {})
            r.initialize('Question?', ['fixture'], research_capacity_tokens=4000)
            seed(r, own=1, child=0, leaf=0)
            with r.store.lock():
                _, memories, equations, _ = r.store.read()
                original = loads(r.store._files()['research/state.json'])
            for total, expected in [(3999,'living'),(4000,'exhausted'),(4001,'exhausted')]:
                s = loads(dumps(original)); s['nodes']['q1']['status']='living'
                model.prompt_tokens = total - 2048
                changes = branching.assess(s, memories, equations, model.model, model.settings, model.count_tokens)
                self.assertEqual(s['nodes']['q1']['status'], expected)
                self.assertEqual(bool(changes), expected=='exhausted')
                self.assertEqual(s['nodes']['q1']['research_capacity']['estimated_tokens'], total)
                self.assertEqual('q1' in s['ripeness_order'], expected=='exhausted')
            s['nodes']['q1']['status']='living'; s['nodes']['q1']['pending_results']='pending'
            branching.assess(s, memories, equations, model.model, model.settings, model.count_tokens)
            self.assertEqual(s['nodes']['q1']['status'], 'living')
            self.assertNotIn('q1', s['ripeness_order'])
            self.assertRaisesRegex(ValueError, 'exhausted', branching.apply, s, 'q1', {'questions':[]}, 'fixture')

    def test_small_token_count_preserves_living_research_despite_large_wire(self):
        with tempfile.TemporaryDirectory() as directory:
            model=CountedModel([{'keywords':['heat', 'transfer']}], prompt_tokens=2500)
            r=Research(directory,model,{})
            r.initialize('Question?', ['fixture'])
            self.assertEqual(r.inspect()['context_budget'],16384)
            seed(r,own=1,child=0,leaf=0,living=('q1',))
            with r.store.lock():
                token,memories,equations,ledger=r.store.read(); state=loads(r.store._files()['research/state.json'])
                m=memories[0]
                m.units.append(Unit(m.allocate('f'),'Detailed evidence',{
                    **m.units[0].fields,'Proposition':('Detailed evidence and limitations. '*1000).strip()}))
                m.revision+=1
                tree.refresh(state,memories)
                r.store.publish(memories,equations,ledger,token,files={'research/state.json':dumps(state)})
            e=r.step()
            self.assertEqual((e['action'],e['status']),('R1','committed'))
            capacity=r.inspect()['nodes']['q1']['research_capacity']
            self.assertGreater(capacity['request_bytes'],16384)
            self.assertEqual(capacity['estimated_tokens'],4548)
            self.assertEqual(r.inspect()['branching_cycles'],0)
            self.assertEqual(read_records(directory)[0]['request']['context_usage']['prompt_tokens'],2500)

    def test_inspection_uses_recorded_tokens_without_recounting_historical_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Experiments(directory).create('tokens')
            model=CountedModel([{'keywords':['heat', 'transfer']}],prompt_tokens=321)
            r=Research(root,model,{}); r.initialize('Question?',['fixture']); r.step()
            model.prompt_tokens=9000
            record=read_records(root)[0]
            viewed=Inspector(directory).decision('tokens',record['id'])
            self.assertEqual(viewed['context_estimate']['prompt_tokens'],321)
            self.assertEqual(viewed['context_estimate']['estimated_total'],2369)
            self.assertEqual(viewed['context_estimate']['basis'],'fixture model tokens')

    def test_r5_is_scheduled_at_the_token_threshold_without_r4(self):
        with tempfile.TemporaryDirectory() as directory:
            model=CountedModel([{'questions':[]}],prompt_tokens=100)
            r=Research(directory,model,{})
            r.initialize('Question?', ['fixture'],research_capacity_tokens=4000)
            seed(r,own=1,child=0,leaf=0,living=('q1',))
            model.prompt_tokens=1952
            event=r.step()
            self.assertEqual((event['action'],event['reason']),('capacity_transition','capacity_transition'))
            self.assertEqual(r.inspect()['nodes']['q1']['status'],'exhausted')
            self.assertFalse(model.requests)
            event=r.step()
            self.assertEqual((event['action'],event['status']),('R5','committed'))
            self.assertEqual(r.inspect()['nodes']['q1']['status'],'split')
            self.assertEqual(len(model.requests),1)
            self.assertEqual(r.inspect()['research_cycles'],0)
            self.assertEqual(r.knowledge.validate()['documents'],1)

    def test_context_limit_and_output_reserve_boundaries(self):
        model=CountedModel(prompt_tokens=14336)
        self.assertFalse(measure('large wire'*3000,2048,16384,model.count_tokens)['over_context_budget'])
        model.prompt_tokens+=1
        self.assertTrue(measure('{}',2048,16384,model.count_tokens)['over_context_budget'])
        with tempfile.TemporaryDirectory() as directory:
            r=Research(directory,model,{})
            self.assertRaisesRegex(ValueError,'active model context',r.initialize,'Q?',['fixture'],context_budget=32768)

    def test_stale_byte_exhaustion_does_not_grant_native_r5(self):
        with tempfile.TemporaryDirectory() as directory:
            model=CountedModel([{'questions':[]}],prompt_tokens=100)
            r=Research(directory,model,{})
            r.initialize('Question?',['fixture'])
            with r.store.lock():
                token,memories,equations,ledger=r.store.read()
                state=loads(r.store._files()['research/state.json'])
                state['nodes']['q1']['status']='exhausted'; tree.refresh(state,memories)
                r.store.publish(memories,equations,ledger,token,files={'research/state.json':dumps(state)})
            event=r.step()
            self.assertEqual(event['status'],'rejected')
            self.assertIn('below current token capacity',event['error'])
            self.assertEqual(r.inspect()['nodes']['q1']['status'],'exhausted')
            self.assertFalse(model.requests)

    def test_r5_prompt_requires_grounding_and_allows_no_children(self):
        text=Path('prompt_templates/R5.txt').read_text()
        self.assertNotIn('You may develop questions not explicitly suggested',text)
        self.assertIn('specific finding, uncertainty, contradiction, limitation or unanswered question',text)
        self.assertIn('An empty list is acceptable',text)
        self.assertIn('root objective',text)
