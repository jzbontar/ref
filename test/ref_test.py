import unittest
import tempfile
import shutil
import os
import re
from pprint import pprint

import ref

class TestRef(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()
        base_dir = os.path.join(self.tempdir, 'ref')
        shutil.copytree('data/ref/', base_dir)
        ref.init(base_dir)

        self.documents = \
             {1: {'author': 'Paterek',
                 'bibtex': '@inproceedings{paterek2007improving,\n  title={Improving regularized singular value decomposition for collaborative filtering},\n  author={Paterek, A.},\n  booktitle={Proceedings of KDD Cup and Workshop},\n  volume={2007},\n  pages={5--8},\n  year={2007}\n}\n',
                 'docid': 1,
                 'filename': 'Paterek - 2007 - Improving regularized singular value decomposition for collaborative filtering - 1.pdf',
                 'journal': 'Proceedings of KDD Cup and Workshop',
                 'notes': '',
                 'rating': 'U',
                 'tags': '',
                 'title': 'Improving regularized singular value decomposition for collaborative filtering',
                 'year': 2007},
             2: {'author': 'Yu, Lo, Hsieh, Lou, McKenzie, Chou, Chung, Ho, Chang, Wei, other',
                 'bibtex': '@inproceedings{yu2010feature,\n  title={Feature engineering and classifier ensemble for KDD cup 2010},\n  author={Yu, H.F. and Lo, H.Y. and Hsieh, H.P. and Lou, J.K. and McKenzie, T.G. and Chou, J.W. and Chung, P.H. and Ho, C.H. and Chang, C.F. and Wei, Y.H. and others},\n  booktitle={Proceedings of the KDD Cup 2010 Workshop},\n  pages={1--16},\n  year={2010}\n}\n',
                 'docid': 2,
                 'filename': 'Yu et al - 2010 - Feature engineering and classifier ensemble for KDD cup 2010 - 2.pdf',
                 'journal': 'Proceedings of the KDD Cup 2010 Workshop',
                 'notes': '',
                 'rating': 'U',
                 'tags': '',
                 'title': 'Feature engineering and classifier ensemble for KDD cup 2010',
                 'year': 2010}}



    def tearDown(self):
        shutil.rmtree(self.tempdir)


    def file_in_docdir(self, fname):
        return os.path.isfile(os.path.join(ref.DOCUMENT_DIR, fname))


    def test_select_documents(self):
        r = [(r['docid'], r['title']) for r in ref.select_documents(['docid', 'title'])]
        self.assertListEqual(r, 
            [(2, 'Feature engineering and classifier ensemble for KDD cup 2010'),
             (1, 'Improving regularized singular value decomposition for collaborative filtering')])

        with self.assertRaises(IndexError):
            ref.select_documents(['docid']).fetchone()['title']

        self.assertListEqual([r['docid'] for r in ref.select_documents('*', order='year ASC')], [1, 2])
        self.assertListEqual([r['docid'] for r in ref.select_documents('*', docids=[1])], [1])
        self.assertDictEqual(dict(ref.select_documents('*', docids=(1,)).fetchone()), self.documents[1])
    

    def test_update_document(self):
        get_doc = lambda: dict(ref.select_documents('*', docids=(2,)).fetchone())

        doc = dict(self.documents[2])
        ref.update_document(doc)
        self.assertDictEqual(self.documents[2], doc)
        self.assertDictEqual(self.documents[2], get_doc())
        self.assertTrue(self.file_in_docdir(doc['filename']))

        doc = \
            {'author': 'author',
             'bibtex': 'bibtex',
             'docid': 2,
             'filename': 'Yu et al - 2010 - Feature engineering and classifier ensemble for KDD cup 2010 - 2.pdf',
             'journal': 'journal',
             'notes': 'notes',
             'rating': 'rating',
             'tags': 'tags',
             'title': 'title',
             'year': 42}
        ref.update_document(dict(doc))
        doc['filename'] = 'author - 42 - title - 2.pdf'
        self.assertDictEqual(doc, get_doc())
        self.assertTrue(self.file_in_docdir(doc['filename']))


    def test_insert_document(self):
        doc = \
            {'author': 'Koren',
             'bibtex': '@inproceedings{koren2008factorization,\n  title={Factorization meets the neighborhood: a multifaceted collaborative filtering model},\n  author={Koren, Y.},\n  booktitle={Proceeding of the 14th ACM SIGKDD international conference on Knowledge discovery and data mining},\n  pages={426--434},\n  year={2008},\n  organization={ACM}\n}\n',
             'docid': 3,
             'filename': 'Koren - 2008 - Factorization meets the neighborhood a multifaceted collaborative filtering model - 3.pdf',
             'journal': 'Proceeding of the 14th ACM SIGKDD international conference on Knowledge discovery and data mining',
             'notes': '',
             'rating': 'U',
             'tags': '',
             'title': 'Factorization meets the neighborhood: a multifaceted collaborative filtering model',
             'year': 2008}

        # normal usecase test
        self.assertEqual(ref.insert_document('data/kdd08koren.pdf'), 3)
        self.assertDictEqual(dict(ref.select_documents('*', docids=[3]).fetchone()), doc)
        self.assertTrue(self.file_in_docdir(doc['filename']))

        # duplicate
        with self.assertRaises(ref.DuplicateError) as e:
            ref.insert_document('data/kdd08koren.pdf')
        self.assertEqual(e.exception.message, doc['filename'])
        
        with self.assertRaises(IOError):
            ref.insert_document('not_exist.pdf')
        with self.assertRaises(IOError):
            ref.insert_document('data')
        with self.assertRaises(ValueError):
            ref.insert_document('ref_test.py')

    def ref_status(self):
        return (
            ref.con.execute('SELECT COUNT(*) FROM documents').fetchone()[0],
            ref.con.execute('SELECT COUNT(*) FROM fulltext').fetchone()[0],
            len(os.listdir(ref.DOCUMENT_DIR)))


    def test_insert_document_transaction1(self):
        ref.con.execute('INSERT INTO documents DEFAULT VALUES')
        with self.assertRaises(AssertionError):
            ref.insert_document('data/kdd08koren.pdf', False)
        self.assertEqual(self.ref_status(), (3, 2, 2))

    def test_insert_document_transaction2(self):
        os.chmod(ref.DOCUMENT_DIR, 0555)
        with self.assertRaises(IOError):
            ref.insert_document('data/kdd08koren.pdf', False)
        os.chmod(ref.DOCUMENT_DIR, 0755)
        self.assertEqual(self.ref_status(), (2, 2, 2))

    def test_delete(self):
        ref.delete_document(1)
        with self.assertRaises(StopIteration):
            ref.delete_document(1)
        self.assertEqual(self.ref_status(), (1, 1, 1))

    def test_delete_transaction1(self):
        os.chmod(ref.DOCUMENT_DIR, 0555)
        with self.assertRaises(OSError):
            ref.delete_document(2)
        self.assertEqual(self.ref_status(), (2, 2, 2))
        os.chmod(ref.DOCUMENT_DIR, 0755)

    def test_search_documents(self):
        search = lambda q: {k: [row['docid'] for row in rows] for k, rows in ref.search_documents(['docid'], q)}

        self.assertDictEqual(search('feature'),
            {'author': [], 'fulltext': [2, 1], 'journal': [], 'notes': [], 'tags': [], 'title': [2]})
        self.assertDictEqual(search('chang'), 
            {'author': [2], 'fulltext': [2], 'journal': [], 'notes': [], 'tags': [], 'title': []})
        
        doc = self.documents[1]
        doc['author'] = doc['journal'] = doc['notes'] = doc['tags'] = doc['title'] = 'foo'
        ref.update_document(doc)
        self.assertDictEqual(search('foo'),
            {'author': [1], 'fulltext': [], 'journal': [1], 'notes': [1], 'tags': [1], 'title': [1]})

        ref.delete_document(1)
        self.assertDictEqual(search('feature'),
            {'author': [], 'fulltext': [2], 'journal': [], 'notes': [], 'tags': [], 'title': [2]})

    def test_get_filename(self):
        doc = self.documents[1]
        self.assertEqual(ref.get_filename(doc), 
            'Paterek - 2007 - Improving regularized singular value decomposition for collaborative filtering - 1.pdf')

        doc['author'] = 'foo, bar, baz, foobar, qux'
        doc['year'] = 42
        doc['title'] = 'Fo!@#$%^&*()+o'
        self.assertEqual(ref.get_filename(doc), 'foo et al - 42 - Foo - 1.pdf')

        
if __name__ == '__main__':
    unittest.main(defaultTest='TestRef.test_get_filename')
    #unittest.main()
