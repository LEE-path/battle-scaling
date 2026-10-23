import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import research


def record(record_id='r1', **changes):
    data = {'record_id': record_id, 'entity_id': 'work-a:hero', 'name': 'Hero',
            'work_id': 'work-a', 'continuity': 'film', 'period': 'ending',
            'state': 'base', 'equipment': ['shield'], 'attributes': ['output'],
            'source_id': 'source-1', 'source_origin': 'primary',
            'source_access': 'read', 'text_kind': 'verbatim_source',
            'exact_text': 'Hero breaks a wall. Chapter 10 page 3.',
            'locator': {'chapter': 10, 'page': 3}, 'snapshot_sha256': 'a' * 64,
            'polarity': 'positive'}
    data.update(changes)
    return data


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = str(Path(self.temp.name) / 'evidence.sqlite3')

    def index(self, *records):
        return research.run({'op': 'index', 'db': self.db, 'records': list(records)})

    def search(self, **values):
        return research.run({'op': 'search', 'db': self.db, **values})

    def test_plan_covers_nine_dimensions_and_both_evidence_directions(self):
        result = research.run({'op': 'plan', 'target': {'entity_id': 'x', 'name': '甲',
            'work_id': 'book', 'continuity': 'novel', 'period': 'ending',
            'state': 'strongest', 'equipment': [], 'medium': 'novel',
            'ending_locator': '终章'}})
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(len(result['dimensions']), 9)
        for dimension in result['dimensions']:
            tasks = [x for x in result['tasks'] if x['attribute'] == dimension]
            self.assertTrue(any(x['polarity'] == 'positive' for x in tasks))
            self.assertTrue(any(x['polarity'] == 'counter' for x in tasks))
        self.assertEqual(result['reading_order'], 'ending_backward_per_attribute')
        self.assertFalse(result['search_executed'])

    def test_plan_missing_identity_does_not_merge_names(self):
        result = research.run({'op': 'plan', 'target': {'name': 'Hero'}})
        self.assertEqual(result['status'], 'needs_scope')
        self.assertIn('entity_id', ' '.join(result['needs']))

    def test_roundtrip_retains_exact_text_locator_hash_and_unknowns(self):
        item = record(extra_fact=None)
        self.assertEqual(self.index(item)['status'], 'ok')
        found = self.search(query='wall')['results'][0]
        self.assertEqual(found, item)
        self.assertIsNone(found['extra_fact'])

    def test_scope_filters_prevent_same_name_cross_version_merge(self):
        self.index(record(), record('r2', entity_id='work-b:hero', work_id='work-b', continuity='comic'),
                   record('r3', state='weakened'), record('r4', equipment=['sword']))
        rows = self.search(query='wall', filters={'entity_id': 'work-a:hero',
            'continuity': 'film', 'state': 'base', 'equipment': ['shield']})['results']
        self.assertEqual([x['record_id'] for x in rows], ['r1'])

    def test_attribute_filter_and_unknown_scope_are_not_zero_or_match(self):
        self.index(record(), record('r2', period=None, attributes=['speed']))
        self.assertEqual(self.search(filters={'period': 'ending', 'attribute': 'speed'})['results'], [])
        self.assertEqual(self.search(filters={'attribute': 'speed'})['results'][0]['period'], None)

    def test_community_cannot_be_promoted_to_verified(self):
        result = self.index(record(source_origin='community', source_access='verified'))
        self.assertEqual(result['status'], 'error')
        self.assertFalse(Path(self.db).exists())

    def test_conflicting_record_ids_do_not_overwrite_source(self):
        self.index(record())
        result = self.index(record(exact_text='replacement'))
        self.assertEqual(result['status'], 'error')
        self.assertEqual(self.search()['results'][0]['exact_text'], record()['exact_text'])

    def test_sql_payload_is_literal_query_and_not_executed(self):
        self.index(record())
        self.assertEqual(self.search(query='" OR 1=1 --')['results'], [])
        self.assertEqual(len(self.search()['results']), 1)

    def test_no_fts_has_explicit_bounded_fallback(self):
        with patch.object(research, '_fts_available', return_value=False):
            self.index(record())
            result = self.search(query='wall')
        self.assertEqual(result['backend'], 'sqlite_like_fallback')
        self.assertTrue(result['warnings'])
        self.assertEqual(len(result['results']), 1)

    def test_chinese_substring_has_explicit_fallback(self):
        self.index(record(exact_text='角色把混凝土墙打穿'))
        result = self.search(query='混凝土')
        self.assertEqual(len(result['results']), 1)
        self.assertIn(result['backend'], ('sqlite_fts5', 'sqlite_like_fallback'))

    def test_coverage_counts_attempts_without_claiming_truth_or_exhaustion(self):
        plan = research.run({'op': 'plan', 'target': {'entity_id': 'x', 'name': '甲',
            'work_id': 'book', 'continuity': 'novel', 'period': 'ending', 'state': 'base'}})
        task = plan['tasks'][0]
        result = research.run({'op': 'coverage', 'plan': plan, 'attempts': [
            {'task_id': task['task_id'], 'status': 'no_results', 'query': 'x',
             'provider': 'official', 'checked_at': '2026-10-20'}]})
        self.assertEqual(result['checked_tasks'], 1)
        self.assertFalse(result['truth_verified'])
        self.assertFalse(result['exhaustive'])
        self.assertGreater(len(result['gaps']), 0)
        self.assertNotIn('power', result)

    def test_cited_import_explicit_and_remains_unverified(self):
        source = Path(self.temp.name) / 'cited.json'
        source.write_text(json.dumps([{'franchise': 'test', 'id': 'hero', 'name': 'Hero',
            'continuity': 'manga', 'feat': 'breaks wall', 'citations': [
            {'locator': 'ch 7', 'claim': 'a feat'}], 'discovery_url': 'https://citedfeats.com/test/'}]), encoding='utf-8')
        result = research.run({'op': 'index', 'db': self.db, 'import_cited': str(source)})
        self.assertEqual(result['status'], 'ok')
        item = self.search()['results'][0]
        self.assertEqual(item['source_origin'], 'community')
        self.assertEqual(item['source_access'], 'indexed')
        self.assertFalse(item['original_source_verified'])
        self.assertEqual(item['citations'][0]['locator'], 'ch 7')
        self.assertEqual(item['license'], 'CC-BY-4.0')
        self.assertEqual(item['license_url'], 'https://creativecommons.org/licenses/by/4.0/')
        self.assertIn('Changes:', item['attribution'])
        self.assertIn(item['source_url'], item['attribution'])
        self.assertFalse(item['attribution_details']['source_authenticity_verified'])
        self.assertEqual(result['import_license_summary']['counts'], {'CC-BY-4.0': 1})

    def cited_index(self, entries):
        source = Path(self.temp.name) / 'cited-rights.json'
        source.write_text(json.dumps(entries), encoding='utf-8')
        return research.run({'op': 'index', 'db': self.db, 'import_cited': str(source)})

    def test_cited_scp_exception_is_share_alike_even_if_row_claims_general_license(self):
        entry = {'franchise': 'scp', 'id': 'scp-096', 'name': 'SCP-096',
            'feat': 'community description', 'license': 'CC BY 4.0',
            'discovery_url': 'https://citedfeats.com/scp/#scp-096',
            'citations': [{'url': 'https://scp-wiki.wikidot.com/scp-096', 'locator': 'Description'}]}
        result = self.cited_index([entry])
        self.assertEqual(result['status'], 'ok')
        item = self.search()['results'][0]
        self.assertEqual(item['license'], 'CC-BY-SA-3.0')
        self.assertEqual(item['license_url'], 'https://creativecommons.org/licenses/by-sa/3.0/')
        self.assertEqual(item['license_basis'], 'scp_row_exception')
        self.assertIn('CC-BY-SA-3.0', item['attribution'])
        self.assertIn('no rights in the cited original works', item['license_scope'])
        self.assertEqual(item['foreign_record'], entry)
        self.assertEqual(item['citations'], entry['citations'])
        self.assertEqual(result['import_license_summary']['counts'], {'CC-BY-SA-3.0': 1})

    def test_cited_mixed_import_keeps_per_row_licenses_and_summary(self):
        result = self.cited_index([
            {'franchise': 'marvel', 'id': 'hero', 'discovery_url': 'https://citedfeats.com/marvel/#hero'},
            {'franchise': 'SCP Foundation', 'franchise_slug': 'scp', 'id': 'scp-096',
             'discovery_url': 'https://citedfeats.com/scp/#scp-096'}])
        self.assertEqual(result['status'], 'ok')
        summary = result['import_license_summary']
        self.assertTrue(summary['mixed_license'])
        self.assertEqual(summary['counts'], {'CC-BY-4.0': 1, 'CC-BY-SA-3.0': 1})
        rows = self.search()['results']
        self.assertEqual({item['license'] for item in rows}, {'CC-BY-4.0', 'CC-BY-SA-3.0'})

    def test_cited_missing_source_keeps_clue_but_does_not_invent_reuse_permission(self):
        result = self.cited_index([
            {'franchise': 'test', 'id': 'one', 'feat': 'a clue'},
            {'franchise': 'scp', 'id': 'two', 'feat': 'another clue', 'discovery_url': None}])
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['added'], 2)
        self.assertEqual(result['import_license_summary']['counts'], {'unresolved': 2})
        self.assertEqual(len(result['import_license_summary']['unresolved_records']), 2)
        for item in self.search()['results']:
            self.assertIsNone(item['license'])
            self.assertIsNone(item['license_url'])
            self.assertEqual(item['license_status'], 'unresolved')
            self.assertTrue(item['rights_needs'])
            self.assertIn('no reuse permission inferred', item['attribution'])
        self.assertTrue(result['warnings'])

    def test_cited_lookalike_domain_does_not_receive_site_license(self):
        result = self.cited_index([{'franchise': 'test', 'id': 'hero',
            'discovery_url': 'https://citedfeats.com.example.org/test/#hero'}])
        self.assertEqual(result['status'], 'ok')
        self.assertIsNone(self.search()['results'][0]['license'])

    def test_cited_scp_source_scope_conflict_is_unresolved_in_both_directions(self):
        result = self.cited_index([
            {'franchise': 'test', 'id': 'one', 'discovery_url': 'https://citedfeats.com/scp/#one'},
            {'franchise': 'scp', 'id': 'two', 'discovery_url': 'https://citedfeats.com/test/#two'}])
        self.assertEqual(result['status'], 'ok')
        for item in self.search()['results']:
            self.assertIsNone(item['license'])
            self.assertIn('SCP franchise and source URL disagree', ' '.join(item['rights_needs']))

    def test_non_cited_records_are_not_given_cited_license_or_attribution(self):
        item = record()
        result = self.index(item)
        self.assertEqual(result['status'], 'ok')
        self.assertIsNone(result['import_license_summary'])
        self.assertEqual(self.search()['results'][0], item)

    def test_cited_anonymous_footer_is_quarantined_not_invented_as_character(self):
        source = Path(self.temp.name) / 'cited-mixed.json'
        source.write_text(json.dumps([
            {'franchise': 'test', 'id': 'hero', 'name': 'Hero', 'feat': 'a feat'},
            {'franchise': 'test', 'id': None, 'name': None, 'rank_text': '27+',
             'discovery_url': 'https://citedfeats.com/test/#'}]), encoding='utf-8')
        result = research.run({'op': 'index', 'db': self.db, 'import_cited': str(source)})
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['added'], 1)
        self.assertEqual(len(result['quarantined']), 1)
        self.assertIsNone(result['quarantined'][0]['record']['id'])

    def test_papers_is_discovery_only_and_uses_bounded_fetch(self):
        raw = Path(self.temp.name) / 'paper.json'
        raw.write_text(json.dumps({'hitCount': 1, 'resultList': {'result': [
            {'id': '1', 'source': 'MED', 'title': 'Bone strength', 'pubYear': '2020',
             'doi': '10.1234/example'}]}}), encoding='utf-8')
        metadata = {'status': 'ok', 'paths': {'raw': str(raw)}, 'sha256': 'b' * 64}
        with patch.object(research.sources, 'fetch_source', return_value=metadata) as fetch:
            result = research.run({'op': 'papers', 'query': 'bone strength',
                'output_dir': self.temp.name, 'limit': 3})
        self.assertEqual(result['status'], 'ok')
        self.assertIn('ebi.ac.uk/europepmc', fetch.call_args.args[0])
        self.assertLessEqual(fetch.call_args.kwargs['max_bytes'], 2 * 1024 * 1024)
        self.assertEqual(result['results'][0]['source_access'], 'indexed')
        self.assertFalse(result['truth_verified'])

    def test_invalid_operation_and_excessive_limit_are_errors(self):
        self.assertEqual(research.run({'op': 'unknown'})['status'], 'error')
        self.index(record())
        self.assertEqual(self.search(limit=100000)['status'], 'error')


if __name__ == '__main__':
    unittest.main()
