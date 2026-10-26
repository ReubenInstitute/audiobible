#!/usr/bin/env python3
from flask import Flask, send_file
from jinja2 import Template
from scriptures import Scriptures

app = Flask(__name__)
s = Scriptures()

HTML = Template("""
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>Audio Bible</title>
	<link rel="stylesheet" href="/@@/styles.css">
</head>
<body>
	{{content}}
	<section class="navigation">
		{% for name, url in links %}
			<a href="{{url}}">{{name}}</a> •
		{% endfor %}
		<a href="/">ראשי</a>
	</section>
</body>
</html>
""")

def render(content, links=[]):
	return HTML.render(content=content, links=links)

def H(template_string, **kwargs):
	return Template(template_string).render(**kwargs)

@app.route('/')
def index():
	h = H("""
	<ul>
		<li><a href="/bible">תנ"ך</a></li>
	</ul>
	""")
	return render(h)

@app.route('/bible')
def bible():
	books = s.bible.books
	h = H("""
	<h1>תנ"ך</h1>
	<ul>
		{% for book in books %}
		<li><a href="/bible/{{book.number}}">{{book.hebrew_name}}</a></li>
		{% endfor %}
	</ul>
	""", books=books)
	return render(h)

@app.route('/bible/<int:book>')
def bible_book(book):
	book = s.bible.books[book - 1]
	h = H("""
	<h1>{{book.hebrew_name}}</h1>
	<ul>
		{% for chapter in book.chapters %}
		<li><a href="/bible/{{book.number}}/{{chapter.number}}">פרק {{chapter.hebrew_fancy_number}}</a></li>
		{% endfor %}
	</ul>
	""", book=book)
	return render(h, [('תנ"ך', '/bible')])

@app.route('/bible/<int:book>/<int:chapter>')
def bible_chapter(book, chapter):
	book = s.bible.books[book - 1]
	chapter = book.chapters[chapter - 1]
	h = H("""
	<h1>{{book.hebrew_name}} - פרק {{chapter.hebrew_fancy_number}}</h1>
	<section class='scriptures'>
		{% for verse in chapter.verses %}
		<span class="verse"><span class="verse-number">{{verse.hebrew_number}}</span> {{verse.text}}</span>
		{% endfor %}
	</section>
	""", book=book, chapter=chapter)
	return render(h, [('תנ"ך', '/bible'), (book.hebrew_name, f'/bible/{book.number}')])

@app.route('/@@/<path:filename>')
def serve_font(filename):
	return send_file(f"fonts/{filename}")

@app.route('/@@/styles.css')
def serve_styles():
	return send_file(f"reubeninstitute/styles.css")

@app.route('/<path:filename>')
def serve_file(filename):
	try:
		return send_file(f"{filename}")
	except FileNotFoundError:
		return "File not found", 404

if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser(description="Audio Bible web viewer (dev server, always debug)")
	parser.add_argument('host', nargs='?', default='127.0.0.1', help="interface to bind (default: 127.0.0.1)")
	parser.add_argument('port', nargs='?', type=int, default=5000, help="port to bind (default: 5000)")
	args = parser.parse_args()
	app.run(host=args.host, port=args.port, debug=True)
