import unittest
import tempfile
import shutil
import os
from pprint import pprint

import ref

class TestRef(unittest.TestCase):
    def setUp(cls):
        cls.tempdir = tempfile.mkdtemp()
        base_dir = os.path.join(cls.tempdir, 'ref')
        shutil.copytree('data/ref/', base_dir)
        ref.init(base_dir)

    def tearDown(cls):
        shutil.rmtree(cls.tempdir)

    def test_select_documents(self):
        r = [(r['docid'], r['title']) for r in ref.select_documents(['docid', 'title'])]
        self.assertListEqual(r, 
            [(2, 'Feature engineering and classifier ensemble for KDD cup 2010'),
             (1, 'Improving regularized singular value decomposition for collaborative filtering')])

        with self.assertRaises(IndexError):
            ref.select_documents(['docid']).fetchone()['title']

        self.assertListEqual([r['docid'] for r in ref.select_documents('*', order='year ASC')], [1, 2])
        self.assertListEqual([r['docid'] for r in ref.select_documents('*', docids=(1,))], [1])
    
    def test_update_document(self):
        get_doc = lambda: dict(ref.select_documents('*', docids=(2,)).fetchone())

        doc = get_doc()
        ref.update_document(dict(doc))
        self.assertDictEqual(doc, get_doc())




if __name__ == '__main__':
    unittest.main()
