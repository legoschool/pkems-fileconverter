"""읽기 엔진: python-docx/pptx가 열지 못하는 파일의 대체 읽기와 .odt 읽기."""
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pkos_readers import read_any  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
T = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"


def make_zip(path, parts):
    with zipfile.ZipFile(path, "w") as z:
        for name, text in parts.items():
            z.writestr(name, text)


class Readers(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def test_docx_without_package_parts_falls_back_to_document_xml(self):
        # [Content_Types].xml이 없어 python-docx가 열지 못하는 문서도 본문 글자는 읽는다
        path = os.path.join(self.dir, "a.docx")
        make_zip(path, {"word/document.xml":
                        f'<w:document xmlns:w="{W}"><w:body><w:p><w:r><w:t>수업 설계</w:t></w:r></w:p>'
                        f'<w:p><w:r><w:t>실습 노트</w:t></w:r></w:p></w:body></w:document>'})
        r = read_any(path)
        self.assertTrue(r.ok, r.error)
        self.assertIn("수업 설계", r.text)
        self.assertIn("실습 노트", r.text)

    def test_pptx_fallback_reads_slides_in_order(self):
        path = os.path.join(self.dir, "b.pptx")
        slide = lambda s: f'<p:sld xmlns:p="x" xmlns:a="{A}"><a:p><a:r><a:t>{s}</a:t></a:r></a:p></p:sld>'
        make_zip(path, {"ppt/slides/slide10.xml": slide("열 번째"), "ppt/slides/slide2.xml": slide("두 번째")})
        r = read_any(path)
        self.assertTrue(r.ok, r.error)
        self.assertLess(r.text.index("두 번째"), r.text.index("열 번째"))

    def test_odt_headings_and_paragraphs(self):
        path = os.path.join(self.dir, "c.odt")
        make_zip(path, {"content.xml":
                        f'<office:document-content xmlns:office="o" xmlns:text="{T}"><office:body><office:text>'
                        f'<text:h text:outline-level="2">협의회 개최</text:h><text:p>일시와 장소</text:p>'
                        f'</office:text></office:body></office:document-content>'})
        r = read_any(path)
        self.assertTrue(r.ok, r.error)
        self.assertIn("## 협의회 개최", r.text)
        self.assertIn("일시와 장소", r.text)


    def test_hwpml_xml_saved_as_hwp(self):
        # 한글에서 XML(HWPML)로 저장한 문서는 문단마다 글자를 꺼낸다
        path = os.path.join(self.dir, "d.hwp")
        with open(path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="utf-8"?><HWPML Version="2.1"><HEAD/><BODY><SECTION>'
                    '<P><TEXT><CHAR>학교안전법</CHAR></TEXT></P><P><TEXT><CHAR>제1조 </CHAR><CHAR>목적</CHAR></TEXT></P>'
                    '</SECTION></BODY></HWPML>')
        r = read_any(path)
        self.assertTrue(r.ok, r.error)
        self.assertIn("학교안전법", r.text)
        self.assertIn("제1조 목적", r.text)

    def test_hwpx_name_with_old_hwp_inside_goes_to_hwp_reader(self):
        # 이름만 .hwpx이고 속은 옛 한글(OLE)인 파일은 zip 오류가 아니라 한글 읽기로 넘어간다
        path = os.path.join(self.dir, "e.hwpx")
        with open(path, "wb") as f:
            f.write(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 600)
        r = read_any(path)
        self.assertNotIn("zip", (r.error or "").lower())


if __name__ == "__main__":
    unittest.main()
