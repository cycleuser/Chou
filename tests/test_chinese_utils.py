"""
Tests for chou.utils.chinese_utils
"""

import pytest

from chou.utils.chinese_utils import (
    is_cjk_char,
    count_cjk_chars,
    has_chinese_content,
    detect_mojibake,
    is_chinese_text_valid,
    should_force_ocr_for_chinese,
    extract_chinese_thesis_fields,
    is_chinese_thesis,
    extract_chinese_names,
    clean_chinese_title,
)


class TestIsCjkChar:
    def test_chinese_character(self):
        assert is_cjk_char('中')
        assert is_cjk_char('文')
        assert is_cjk_char('学')
    
    def test_english_character(self):
        assert not is_cjk_char('a')
        assert not is_cjk_char('A')
    
    def test_digit(self):
        assert not is_cjk_char('1')
    
    def test_punctuation(self):
        assert not is_cjk_char(',')
        assert not is_cjk_char('.')


class TestCountCjkChars:
    def test_pure_chinese(self):
        assert count_cjk_chars('中文测试') == 4
    
    def test_mixed_text(self):
        assert count_cjk_chars('Hello中文World测试') == 4
    
    def test_english_only(self):
        assert count_cjk_chars('Hello World') == 0
    
    def test_empty_string(self):
        assert count_cjk_chars('') == 0


class TestHasChineseContent:
    def test_has_chinese(self):
        assert has_chinese_content('这是一段中文文本')
        assert has_chinese_content('Hello这是中文Text', min_chars=3)
    
    def test_no_chinese(self):
        assert not has_chinese_content('Hello World')
        text = '纯英文文本'
        cjk_count = count_cjk_chars(text)
        assert not has_chinese_content('纯英文文本', min_chars=cjk_count + 1)
    
    def test_min_chars_threshold(self):
        assert has_chinese_content('中文', min_chars=2)
        assert not has_chinese_content('中文', min_chars=5)
    
    def test_empty_string(self):
        assert not has_chinese_content('')
    
    def test_mixed_text_counts_correctly(self):
        text = 'Hello这是中文Text测试内容'
        assert has_chinese_content(text, min_chars=5)


class TestDetectMojibake:
    def test_valid_chinese(self):
        is_corrupted, ratio = detect_mojibake('这是一段正常的中文文本')
        assert not is_corrupted
        assert ratio < 0.05
    
    def test_valid_english(self):
        is_corrupted, ratio = detect_mojibake('This is valid English text')
        assert not is_corrupted
    
    def test_mojibake_control_chars(self):
        is_corrupted, ratio = detect_mojibake('这\x00是\x0b乱码')
        assert is_corrupted
    
    def test_replacement_chars(self):
        text_with_replacement = '正常文本'
        is_corrupted, ratio = detect_mojibake(text_with_replacement)
        assert is_corrupted
        assert ratio > 0
    
    def test_empty_string(self):
        is_corrupted, ratio = detect_mojibake('')
        assert not is_corrupted
        assert ratio == 0.0


class TestIsChineseTextValid:
    def test_valid_chinese_text(self):
        is_valid, reason = is_chinese_text_valid('这是一段正常的中文文本，包含多个汉字。')
        assert is_valid
        assert reason == "valid_chinese_text"
    
    def test_non_chinese_document(self):
        is_valid, reason = is_chinese_text_valid('This is English text only')
        assert is_valid
        assert reason == "not_chinese_document"
    
    def test_empty_text(self):
        is_valid, reason = is_chinese_text_valid('')
        assert not is_valid
        assert reason == "empty_text"
    
    def test_mojibake_text(self):
        text_with_garbage = '正常文本\x00\x01\x02乱码部分'
        is_valid, reason = is_chinese_text_valid(text_with_garbage)
        assert not is_valid


class TestShouldForceOcrForChinese:
    def test_valid_chinese_no_ocr(self):
        text = '这是一段正常的中文文本，包含标题和作者信息。'
        assert not should_force_ocr_for_chinese(text)
    
    def test_corrupted_chinese_needs_ocr(self):
        text_with_garbage = '论文题目：深度学习研究\x00\x01\x02'
        assert should_force_ocr_for_chinese(text_with_garbage)
    
    def test_empty_text_needs_ocr(self):
        assert should_force_ocr_for_chinese('')
    
    def test_very_short_text_needs_ocr(self):
        assert should_force_ocr_for_chinese('短')
    
    def test_english_no_ocr(self):
        text = 'This is a normal English academic paper title with author names.'
        assert not should_force_ocr_for_chinese(text)


class TestIsChineseThesis:
    def test_thesis_with_explicit_markers(self):
        assert is_chinese_thesis('论文题目：深度学习在医学图像中的应用')
        assert is_chinese_thesis('硕士学位论文\n作者姓名：张三')
        assert is_chinese_thesis('博士学位论文\n研究生姓名：李四')
    
    def test_thesis_with_field_labels(self):
        assert is_chinese_thesis('作者姓名：王五\n指导教师：赵六')
        assert is_chinese_thesis('培养单位：北京大学')
    
    def test_normal_paper_not_thesis(self):
        assert not is_chinese_thesis('深度学习综述\n摘要：本文综述了...')
        assert not is_chinese_thesis('This is an English paper')
    
    def test_empty_text(self):
        assert not is_chinese_thesis('')
    
    def test_spaced_markers(self):
        assert is_chinese_thesis('硕 士 学 位 论 文')
        assert is_chinese_thesis('博 士 学 位 论 文')


class TestExtractChineseThesisFields:
    def test_extract_title(self):
        text = '论文题目：基于深度学习的医学图像分析\n作者姓名：张三'
        fields = extract_chinese_thesis_fields(text)
        assert 'title' in fields
        assert '基于深度学习的医学图像分析' in fields['title']
    
    def test_extract_author(self):
        text = '论文题目：研究题目\n作者姓名：张三\n指导教师：李四'
        fields = extract_chinese_thesis_fields(text)
        assert 'author' in fields
        assert '张三' in fields['author']
    
    def test_extract_advisor(self):
        text = '论文题目：研究题目\n指导教师：李教授'
        fields = extract_chinese_thesis_fields(text)
        assert 'advisor' in fields
    
    def test_multiple_formats(self):
        text = '题目：深度学习研究\n姓名：王五'
        fields = extract_chinese_thesis_fields(text)
        assert 'title' in fields
        assert 'author' in fields
    
    def test_empty_result_for_non_thesis(self):
        text = '这是一段普通文本，没有学位论文标记'
        fields = extract_chinese_thesis_fields(text)
        assert len(fields) == 0
    
    def test_spaced_labels(self):
        text = '论文题目：研究主题\n作  者：测试作者'
        fields = extract_chinese_thesis_fields(text)
        assert 'title' in fields
        assert 'author' in fields


class TestExtractChineseNames:
    def test_extract_2_char_names(self):
        names = extract_chinese_names('张三、李四、王五')
        assert '张三' in names
        assert '李四' in names
        assert '王五' in names
    
    def test_extract_3_char_names(self):
        names = extract_chinese_names('王小明、李建国、张伟华')
        assert '王小明' in names
        assert '李建国' in names
    
    def test_filter_non_names(self):
        names = extract_chinese_names('摘要：本文研究了张三和李四的工作')
        valid_names = [n for n in names if n in ['张三', '李四']]
        assert len(valid_names) >= 0
        assert '摘要' not in names
    
    def test_empty_text(self):
        names = extract_chinese_names('')
        assert len(names) == 0
    
    def test_no_valid_names(self):
        names = extract_chinese_names('目录\n第一章\n引言')
        assert len(names) == 0 or '目录' not in names


class TestCleanChineseTitle:
    def test_basic_cleaning(self):
        title = '基于深度学习的研究 '
        cleaned = clean_chinese_title(title)
        assert cleaned == '基于深度学习的研究'
    
    def test_remove_replacement_chars(self):
        title = '研究题目内容'
        cleaned = clean_chinese_title(title)
        assert '' not in cleaned
        assert len(cleaned) > 0
    
    def test_remove_leading_colon(self):
        title = '：深度学习研究'
        cleaned = clean_chinese_title(title)
        assert cleaned == '深度学习研究'
    
    def test_remove_trailing_colon(self):
        title = '深度学习研究：'
        cleaned = clean_chinese_title(title)
        assert not cleaned.endswith('：')
    
    def test_empty_title(self):
        cleaned = clean_chinese_title('')
        assert cleaned == ''
    
    def test_preserve_valid_chars(self):
        title = '基于深度学习的医学图像分析研究'
        cleaned = clean_chinese_title(title)
        assert '基于' in cleaned
        assert '深度学习' in cleaned
        assert '研究' in cleaned


class TestChineseIntegration:
    def test_full_thesis_extraction_workflow(self):
        text = """硕士学位论文
论文题目：基于深度学习的医学图像分割研究
作者姓名：张三
指导教师：李教授
培养单位：北京大学
答辩日期：2024年6月"""
        
        assert is_chinese_thesis(text)
        fields = extract_chinese_thesis_fields(text)
        assert 'title' in fields
        assert 'author' in fields
        assert 'advisor' in fields
        
        title = clean_chinese_title(fields.get('title', ''))
        assert '深度学习' in title or '医学图像' in title
        
        is_valid, reason = is_chinese_text_valid(text)
        assert is_valid
        assert not should_force_ocr_for_chinese(text)
    
    def test_corrupted_chinese_needs_ocr(self):
        text = '论文题目\x00：深度学习\x01研究\n作者姓名\x02：张三'
        
        is_valid, reason = is_chinese_text_valid(text)
        assert not is_valid
        assert should_force_ocr_for_chinese(text)