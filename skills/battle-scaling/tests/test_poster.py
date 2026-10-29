import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import poster


class PosterTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.left, self.right = self.root / 'left.png', self.root / 'right.png'
        Image.new('RGB', (400, 600), 'red').save(self.left)
        Image.new('RGB', (1000, 600), 'blue').save(self.right)

    def test_native_template_composition_and_original_preservation(self):
        from PIL import Image
        before = self.left.read_bytes()
        output = poster.compose(left=self.left, right=self.right, left_name='甲', right_name='乙',
                                output=self.root / 'poster.png', left_fit='contain')
        with Image.open(output) as image:
            self.assertEqual(image.size, (1920, 1080))
            self.assertEqual(image.getpixel((50, 400)), (255, 0, 0))
            self.assertEqual(image.getpixel((1850, 400)), (0, 0, 255))
        self.assertEqual(self.left.read_bytes(), before)
        with self.assertRaises(ValueError):
            poster.compose(left=self.left, right=self.right, left_name='甲', right_name='乙', output=self.left)

    def test_flat_cover_is_not_accepted_as_transparent_overlay(self):
        from PIL import Image
        flat = self.root / 'flat.png'
        Image.new('RGB', (1920, 1080), 'white').save(flat)
        with self.assertRaisesRegex(ValueError, 'transparent'):
            poster.compose(left=self.left, right=self.right, left_name='甲', right_name='乙',
                           output=self.root / 'poster.png', template=flat)

    def test_report_and_implicit_rating_are_not_default_inputs(self):
        with self.assertRaises(SystemExit):
            poster.main(['--left', str(self.left), '--right', str(self.right), '--left-name', '甲',
                         '--right-name', '乙', '--output', str(self.root / 'poster.png'), '--rating', '爆城'])
        with self.assertRaisesRegex(ValueError, 'single-line'):
            poster.compose(left=self.left, right=self.right, left_name='甲\n评级：爆城', right_name='乙',
                           output=self.root / 'poster.png')

    def test_contain_preserves_the_whole_portrait(self):
        from PIL import Image, ImageDraw
        image = Image.new('RGBA', (100, 400), 'blue')
        ImageDraw.Draw(image).rectangle((0, 0, 99, 30), fill='red')
        result = poster.side_image(image, (400, 400), fit='contain')
        self.assertEqual(result.getpixel((200, 10)), (255, 0, 0, 255))
        self.assertEqual(result.getpixel((200, 390)), (0, 0, 255, 255))


if __name__ == '__main__':
    unittest.main()
