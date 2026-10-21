import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import tieba
import site_registry


def page(pn=1, total=1, items=None, more=False):
    return {'status': 'ok', 'page': {'current_page': pn, 'total_page': total, 'has_more': more},
            'items': items if items is not None else [post(1)],
            'thread': {'tid': '123', 'title': 'Test'}, 'forum': {'name': '汪峰在'}}


def post(pid, replies=0, **changes):
    return {'tid': '123', 'pid': str(pid), 'floor': pid, 'text': 'public text',
            'author': {'name': 'name'}, 'reply_num': replies, **changes}


class TiebaCollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.request = {'op': 'thread', 'tid': '123', 'output_dir': str(self.root / 'out'),
                        'python': sys.executable, 'db': str(self.root / 'sites.sqlite3'), 'delay': 0.5}

    def run_with(self, responses, **changes):
        with patch.object(tieba, '_call_worker', side_effect=responses) as worker, \
                patch.object(tieba.time, 'sleep'):
            result = tieba.run({**self.request, **changes})
            calls = worker.call_count
        data = json.loads(Path(result['result']).read_text(encoding='utf-8'))
        return result, data, calls

    def test_pagination_deduplicates_ids_and_preserves_sources(self):
        result, data, count = self.run_with([
            page(1, 2, [post(1), post(2)], True), page(2, 2, [post(2), post(4)])])
        self.assertEqual(result['status'], 'ok')
        self.assertEqual([p['pid'] for p in data['items']], ['1', '2', '4'])
        self.assertEqual(result['coverage']['main']['pages'], [1, 2])
        self.assertEqual(count, 2)
        self.assertTrue(all(p['source_id'] and p['source_locator'] for p in data['items']))
        events = site_registry.run({'op': 'history', 'domain': 'tieba.baidu.com',
                                   'db': self.request['db'], 'include_seeds': False})['events']
        self.assertEqual({p['url'] for p in events},
                         {'https://tieba.baidu.com/p/123?pn=1', 'https://tieba.baidu.com/p/123?pn=2'})
        self.assertTrue(all(p['outcome'] == 'fetched_unreviewed' for p in events))

    def test_page_cap_is_partial_and_resume_fetches_only_missing_pages(self):
        first, _, _ = self.run_with([page(1, 2, [post(1)], True)], max_pages=1)
        self.assertEqual(first['status'], 'partial')
        second, _, count = self.run_with([page(2, 2, [post(2)])], max_pages=2)
        self.assertEqual(second['status'], 'ok')
        self.assertEqual(second['resumed_pages'], 1)
        self.assertEqual(count, 1)

    def test_changed_saved_page_is_rejected_without_network_request(self):
        self.run_with([page()])
        saved = next((self.root / 'out' / 'pages').glob('*.json'))
        saved.write_text('{}', encoding='utf-8')
        with patch.object(tieba, '_call_worker') as worker:
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                tieba.run(self.request)
        worker.assert_not_called()

    def test_repeated_page_and_wrong_page_never_claim_complete(self):
        result, _, _ = self.run_with([page(1, 2, [post(1)], True), page(2, 2, [post(1)])])
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['coverage']['main']['reason'], 'repeated page response')
        other = {**self.request, 'output_dir': str(self.root / 'wrong')}
        with patch.object(tieba, '_call_worker', return_value=page(2, 2)):
            result = tieba.run(other)
        self.assertFalse(result['coverage']['main']['complete'])

    def test_subreplies_fetched_separately_and_tracked_per_parent(self):
        result, data, count = self.run_with([
            page(items=[post(1, 2), post(2, 0)]),
            page(items=[post(11), post(12)])], include_subreplies=True)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(count, 2)
        self.assertTrue(result['coverage']['subreplies_complete'])
        self.assertEqual([x['parent_pid'] for x in data['comments']], ['1', '1'])

    def test_blocked_reply_stops_further_requests_and_retains_main_posts(self):
        result, data, count = self.run_with([
            page(items=[post(1, 2), post(2, 3)]),
            {'status': 'blocked', 'error': {'message': 'captcha'}}], include_subreplies=True)
        self.assertEqual(count, 2)
        self.assertEqual(len(data['items']), 2)
        self.assertEqual(result['status'], 'partial')
        self.assertFalse(result['coverage']['subreplies_complete'])

    def test_request_budget_leaves_explicit_missing_coverage(self):
        result, _, count = self.run_with([page(1, 9, [post(1)], True)], max_requests=1)
        self.assertEqual(count, 1)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['coverage']['main']['reason'], 'max_requests reached')

    def test_large_search_page_count_is_metadata_not_a_scan_instruction(self):
        items = [post(1, tid='321', is_excerpt=True), post(2, tid='321', is_excerpt=True)]
        result, data, count = self.run_with([page(1, 3581205, items, True)],
                                          op='search', query='量级', max_pages=1)
        self.assertEqual(count, 1)
        self.assertEqual(len(data['items']), 2)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['coverage']['main']['reported_total_pages'], 3581205)

    def test_images_preserve_supplied_variants_without_url_rewriting(self):
        image = {'url': 'https://tiebapic.baidu.com/forum/pic/item/a.jpg',
                 'original_url': 'https://tiebapic.baidu.com/forum/pic/item/a.jpg',
                 'thumbnail_url': 'https://tiebapic.baidu.com/forum/w%3D580/a.jpg'}
        result, data, _ = self.run_with([page(items=[post(1, images=[image])])])
        self.assertEqual(result['counts']['image_urls'], 2)
        self.assertEqual({x['url'] for x in data['media']}, {image['url'], image['thumbnail_url']})

    def test_invalid_targets_credentials_boolean_values_and_output_are_rejected(self):
        invalid = [{'url': 'http://127.0.0.1/p/123'}, {'url': 'https://tieba.baidu.com.evil.org/p/123'},
                   {'url': 'https://tieba.baidu.com/p/124'}, {'cookie': 'secret'},
                   {'tid': True}, {'only_thread_author': 'false'}, {'max_pages': 0},
                   {'delay': 0}, {'output_dir': str(tieba.ROOT)}]
        for changes in invalid:
            with self.subTest(changes=changes), patch.object(tieba, '_call_worker') as worker:
                with self.assertRaises(ValueError):
                    tieba.run({**self.request, **changes})
                worker.assert_not_called()

    def test_different_thread_cannot_overwrite_the_same_job(self):
        self.run_with([page()])
        with self.assertRaisesRegex(ValueError, 'different Tieba job'):
            tieba.run({**self.request, 'tid': '456'})

    def test_conflicting_pagination_is_never_complete(self):
        for i, response in enumerate([
                page(1, 3, [post(1)], False), page(1, 1, [post(1)], True),
                page(1, 0, [post(1)], False)]):
            result, _, _ = self.run_with([response], output_dir=str(self.root / str(i)))
            self.assertEqual(result['status'], 'partial')
            self.assertEqual(result['coverage']['main']['reason'], 'pagination_conflict')

    def test_refresh_preserves_old_capture_and_ledger_locators(self):
        first, old, _ = self.run_with([page(items=[post(1)])])
        source = old['sources'][0]
        original = Path(source['path']).read_bytes()
        second, new, count = self.run_with([page(items=[post(2)])], resume=False)
        self.assertEqual(count, 1)
        self.assertNotEqual(source['path'], new['sources'][0]['path'])
        self.assertEqual(Path(source['path']).read_bytes(), original)
        self.assertEqual(source['sha256'], tieba.hashlib.sha256(original).hexdigest())

    def test_all_cached_rerun_keeps_original_capture_times_and_no_live_claim(self):
        _, old, _ = self.run_with([page()])
        result, new, count = self.run_with([])
        self.assertEqual(count, 0)
        self.assertFalse(result['freshness']['live_revalidated'])
        self.assertEqual(new['sources'][0]['captured_at'], old['sources'][0]['captured_at'])

    def test_blocked_main_pagination_does_not_start_reply_requests(self):
        result, _, count = self.run_with([
            page(1, 2, [post(1, 2)], True), {'status': 'blocked', 'error': {'message': 'captcha'}}],
            include_subreplies=True)
        self.assertEqual(count, 2)
        self.assertFalse(result['coverage']['main']['complete'])
        self.assertFalse(result['coverage']['subreplies_complete'])

    def test_same_image_keeps_multiple_floor_usages(self):
        image = {'url': 'https://tiebapic.baidu.com/forum/pic/item/shared.jpg'}
        result, data, _ = self.run_with([page(items=[post(1, images=[image]), post(2, images=[image])])])
        self.assertEqual(result['counts']['image_urls'], 1)
        self.assertEqual({x['post_id'] for x in data['media'][0]['usages']}, {'1', '2'})


if __name__ == '__main__':
    unittest.main()
