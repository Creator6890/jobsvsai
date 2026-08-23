"""Static RSS/Atom documents for ingestion tests. No test touches a live feed."""

RSS_VALID = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Pytest Lab Blog</title>
    <item>
      <title>Introducing GPT-Pytest</title>
      <link>https://pytest-lab.example.com/gpt-pytest?utm_source=rss&amp;utm_medium=feed</link>
      <description><![CDATA[<p>A new <b>frontier model</b> with improved reasoning.</p><script>alert(1)</script>]]></description>
      <pubDate>Fri, 21 Aug 2026 10:00:00 GMT</pubDate>
      <category>Research</category>
      <category>Models</category>
    </item>
    <item>
      <title>Pytest Lab appoints new chief financial officer</title>
      <link>https://pytest-lab.example.com/cfo-appointment</link>
      <description>The company names a new CFO after a funding round.</description>
      <pubDate>Fri, 21 Aug 2026 09:00:00 GMT</pubDate>
    </item>
    <item>
      <title>GPT-Pytest is now available</title>
      <link>https://pytest-lab.example.com/gpt-pytest-available</link>
      <description>The model ships to all customers today.</description>
      <pubDate>Fri, 21 Aug 2026 11:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

ATOM_VALID = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Pytest Atom Lab</title>
  <entry>
    <title>Our AI agent can now use a computer to complete tasks</title>
    <link rel="alternate" href="https://pytest-atom.example.com/agent-computer-use"/>
    <link rel="edit" href="https://pytest-atom.example.com/edit/1"/>
    <summary>Agentic tool use for developer workflows and automation.</summary>
    <published>2026-08-21T12:00:00Z</published>
    <category term="agents"/>
  </entry>
  <entry>
    <title>Malformed entry with no link</title>
    <summary>This entry has no link element and must be skipped.</summary>
    <published>2026-08-21T13:00:00Z</published>
  </entry>
</feed>"""

# Well-formed XML, wrong vocabulary.
NOT_A_FEED = """<?xml version="1.0"?><html><body><p>Not a feed</p></body></html>"""

# Truncated: not parseable at all.
MALFORMED_XML = """<?xml version="1.0"?><rss version="2.0"><channel><item><title>Broken"""

# Billion laughs. defusedxml must refuse this rather than expanding it.
ENTITY_BOMB = """<?xml version="1.0"?>
<!DOCTYPE lolz [
 <!ENTITY lol "lol">
 <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
 <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
]>
<rss version="2.0"><channel><item><title>&lol3;</title>
<link>https://evil.example.com/x</link></item></channel></rss>"""

# An entry whose summary is hostile HTML.
RSS_HOSTILE_HTML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Hostile</title>
  <item>
    <title>AI model launch with messy summary</title>
    <link>https://hostile.example.com/post</link>
    <description><![CDATA[<script>steal()</script><style>body{}</style><p>Real  text &amp; entities</p><img src=x onerror=alert(1)>]]></description>
    <pubDate>Fri, 21 Aug 2026 08:00:00 GMT</pubDate>
  </item>
</channel></rss>"""
