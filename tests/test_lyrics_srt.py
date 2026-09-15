"""Original text, timing defects, and portable input/output protection.
SPDX-License-Identifier: GPL-3.0-or-later
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import lyrics_srt as align


class AlignmentTests(unittest.TestCase):
    def test_original_text_and_punctuation_are_preserved(self):
        words, lines, audit = align.parse_alignment('假\t0.1\t0.3\n乙\t0.3\t0.5\n丙\t1\t2', ['“甲，乙！”', '丙。'], 3)
        self.assertEqual(lines[0]['text'], '“甲，乙！”')
        self.assertEqual(''.join(w['text'] for w in words), '“甲，乙！”丙。')
        self.assertEqual(audit['text_replacements'], [{'row':1,'returned':'假','original':'甲'}])

    def test_defects_are_reported_without_inventing_timing(self):
        words, _, audit = align.parse_alignment('甲\t0\t0\n乙\t0.1\t3\n丙\t2.9\t3.5', ['甲乙丙'], 4)
        self.assertEqual(words[0]['start'], words[0]['end'])
        self.assertEqual(len(audit['zero_duration']), 1)
        self.assertEqual(len(audit['longer_than_2s']), 1)
        self.assertEqual(len(audit['overlaps']), 1)
        self.assertFalse(audit['listening_verified'])

    def test_missing_text_cannot_be_positionally_filled(self):
        with self.assertRaisesRegex(ValueError, 'length differs'):
            align.parse_alignment('甲\t0\t1', ['甲乙'], 2)

    def test_token_must_not_cross_lyric_lines(self):
        with self.assertRaisesRegex(ValueError, 'crosses'):
            align.parse_alignment('甲乙\t0\t1', ['甲','乙'], 2)

    def test_rejects_nonfinite_outside_negative_and_reversed_times(self):
        for raw in ('甲\tnan\t1', '甲\t0\tinf', '甲\t0\t10', '甲\t-1\t1', '甲\t2\t1'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                align.parse_alignment(raw, ['甲'], 3)
        with self.assertRaisesRegex(ValueError, 'out of order'):
            align.parse_alignment('甲\t1\t2\n乙\t0\t0.5', ['甲乙'], 3)

    def test_srt_rounding_defect_is_visible(self):
        _, _, audit = align.parse_alignment('甲\t0.1001\t0.1002', ['甲'], 2)
        self.assertEqual(audit['zero_duration'], [])
        self.assertEqual(audit['srt_zero_duration'], [1])

    def test_lyrics_encoding_and_section_tags(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'lyrics.txt'
            for encoding in ('utf-8-sig','utf-16','gb18030'):
                p.write_bytes('[Verse 1]\n甲，乙。\n[Chorus]\n丙丁\n'.encode(encoding))
                self.assertEqual(align.lyric_lines(p), ['甲，乙。','丙丁'])

    def test_portable_prepare_and_finalize_protect_sources_and_versions(self):
        with tempfile.TemporaryDirectory(prefix='字幕 中文 ') as root:
            root=Path(root); audio=root/'own.wav'; lyrics=root/'own.txt'; tsv=root/'result.tsv'
            with wave.open(str(audio),'wb') as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes(b'\0\0'*480000)
            lyrics.write_text('甲乙\n丙丁', encoding='utf-8')
            tsv.write_text('甲\t0.1\t1\n乙\t1\t2\n丙\t2\t2\n丁\t3\t4', encoding='utf-8')
            before={p.name:align.sha256(p) for p in (audio,lyrics,tsv)}
            with patch.object(align.subprocess,'run') as probe:
                probe.return_value.stdout=json.dumps({'format':{'duration':'10'}}).encode()
                align.prepare(audio, lyrics, root/'job')
            graph=align.read(root/'job/workflow.api.json')
            self.assertEqual(graph['15']['inputs']['text'], '甲乙\n丙丁')
            self.assertIs(graph['15']['inputs']['segment_by_sentence'], False)
            self.assertNotIn(str(root), (root/'job/alignment-job.json').read_text('utf-8'))
            result=align.finalize(root/'job',tsv,root/'output')
            self.assertEqual(result['zero_duration'],1)
            self.assertIn('甲乙', (root/'output/lines.srt').read_text('utf-8-sig'))
            self.assertEqual(before,{p.name:align.sha256(p) for p in (audio,lyrics,tsv)})
            with self.assertRaises(FileExistsError): align.finalize(root/'job',tsv,root/'output')
            (root/'job/original-lyrics.txt').write_text('改了',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Frozen'): align.finalize(root/'job',tsv,root/'other')
            self.assertFalse((root/'other').exists())


if __name__=='__main__': unittest.main()
