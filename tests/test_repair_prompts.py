"""The definition instruction supplements the existing source-grounding contract."""
from pathlib import Path
import unittest


class DefinitionInstructionTests(unittest.TestCase):
    def test_only_authorized_sentence_is_added_to_r3(self):
        root = Path(__file__).resolve().parents[1]
        instruction = (
            'When a supplied research passage explicitly defines a selected technical term, '
            'return the complete verbatim definitional statement in `definition` rather than null. '
            'Otherwise return null. Do not paraphrase, infer, or supply a definition from background knowledge.'
        )
        prompt = (root / 'prompt_templates/R3.txt').read_text()
        self.assertEqual(prompt.count(instruction), 1)
        self.assertGreater(prompt.index(instruction), prompt.index('IMPORTANT TERMINOLOGY'))
        self.assertIn('Passages must occur verbatim in the supplied source content', prompt)
        self.assertIn('Python validates optional terms independently of substantive results.', prompt)
