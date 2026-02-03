SUMMARY_SYSTEM = "You are a helpful assistant that writes factual newsletter summaries."

SUMMARY_TEMPLATE = """
Style: {style}
Length: {length}
Tone: {tone}
Language: {language}

Content:
{content}

Write a concise summary. If there are important links in the content, mention them in the summary.
"""
