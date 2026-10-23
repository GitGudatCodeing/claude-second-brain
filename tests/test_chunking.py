import server


def test_headings_become_a_path():
    text = "# Top\nintro\n## Child\nbody\n### Grandchild\ndeep\n## Sibling\nside\n"
    heads = [h for h, _ in server.chunk_text(text, is_markdown=True)]
    assert heads == ["Top", "Top > Child", "Top > Child > Grandchild", "Top > Sibling"]


def test_hash_lines_inside_code_fences_are_not_headings():
    text = "# Real\n```bash\n# just a comment\necho hi\n```\n"
    chunks = server.chunk_text(text, is_markdown=True)
    assert [h for h, _ in chunks] == ["Real"]
    assert "# just a comment" in chunks[0][1]


def test_non_markdown_keeps_hash_lines_as_text():
    chunks = server.chunk_text("# a python comment\nx = 1\n", is_markdown=False)
    assert chunks == [("", "# a python comment\nx = 1")]


def test_empty_sections_are_dropped():
    assert server.chunk_text("# A\n\n# B\ntext\n", is_markdown=True) == [("B", "text")]


def test_long_text_is_split_near_chunk_size():
    paras = "\n\n".join(f"paragraph {i} " + "word " * 60 for i in range(20))
    chunks = server.chunk_text(paras, is_markdown=True)
    assert len(chunks) > 1
    assert all(len(t) <= server.CHUNK_CHARS * 1.5 for _, t in chunks)
    assert "paragraph 0" in chunks[0][1] and "paragraph 19" in chunks[-1][1]


def test_one_huge_paragraph_is_cut():
    line = "x" * 100
    huge = "\n".join([line] * 60)  # 6000 chars, no blank lines
    chunks = server.chunk_text(huge, is_markdown=False)
    assert len(chunks) >= 4
    assert sum(len(t) for _, t in chunks) >= len(huge) - 100
