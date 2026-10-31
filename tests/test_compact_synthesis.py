"""Compact synthesis provenance and verbose-format compatibility."""
from copy import deepcopy
import unittest

from mira.format import Memory, Unit, Relationship, parse, render, loads


class CompactSynthesisTests(unittest.TestCase):
    def memory(self):
        m = Memory('s1', 'Combined scientific evidence', 'Scope, uncertainty and limitations.', revision=3,
            metadata={'kind': 'synthesis', 'node_id': 'q1', 'created_order': 4, 'markdown_format': 2,
                'source_memories': ['r1', 'r2'], 'synthesized_by': None,
                'synthesis_inputs': [{'memory_id': 'r1', 'memory_sha256': 'a' * 64,
                    'representation': 'complete_memory', 'supplied_units': ['r1#f1', 'r1#q1']}]})
        m.units = [Unit(m.allocate('f'), 'Descriptive scientific label', {'Kind': 'synthesis',
            'Evidence status': 'unverified', 'Proposition': 'The findings agree within the reported limits.',
            'Explanation': 'Source one reports a claim.\n\nSource two reports limited observations.',
            'Provenance': 'Interpretation restricted to supplied sources; uncertainty remains.'})]
        m.relationships = [Relationship('f1', 'SYNTHESIZES', 'r1#f1', 'unverified'),
                           Relationship('f1', 'SYNTHESIZES', 'r2#f2', 'unverified')]
        return m

    def test_compact_synthesis_round_trip_preserves_all_fields_and_anchors(self):
        original = self.memory(); text = render(original)
        self.assertEqual(parse(text), original)
        self.assertIn('## Summary\n', text); self.assertIn('## Knowledge\n', text)
        self.assertIn('### #f1 | Descriptive scientific label', text)
        self.assertNotIn('Kind:', text); self.assertNotIn('**Proposition:**', text)
        self.assertNotIn('conclusion', text)
        self.assertIn('Evidence status: unverified', text)
        header = loads(text.split('```json\n', 1)[1].split('\n```', 1)[0])
        self.assertEqual(header['version'], 2); self.assertNotIn('summary', header)
        self.assertEqual(len(text.split('```json\n', 1)[1].split('\n```', 1)[0].splitlines()), 1)
        self.assertEqual(parse(text).units[0].fields['Kind'], 'synthesis')

    def test_verbose_synthesis_stays_readable_without_implicit_conversion(self):
        legacy = self.memory(); legacy.metadata.pop('markdown_format')
        old = render(legacy)
        self.assertIn('## Memory\n', old); self.assertEqual(parse(old), legacy)
        self.assertEqual(render(parse(old)), old)
        converted = deepcopy(legacy); converted.metadata['markdown_format'] = 2
        self.assertEqual(parse(render(converted)), converted)
        self.assertEqual(converted.units, legacy.units)
        self.assertEqual(converted.relationships, legacy.relationships)
        self.assertEqual(converted.next_ids, legacy.next_ids)

    def test_plain_label_never_becomes_synthesis_kind(self):
        text = render(self.memory()).replace('Descriptive scientific label', 'Observation across studies')
        self.assertEqual(parse(text).units[0].fields['Kind'], 'synthesis')
