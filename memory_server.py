from flask import Flask
import os

app = Flask(__name__)

@app.route('/')
def serve_memory():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'MEMORY.md')
    if not os.path.exists(path):
        return 'MEMORY.md not found', 404
    with open(path, encoding='utf-8') as f:
        return f.read(), 200, {'Content-Type': 'text/plain; charset=utf-8'}

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8051))
    app.run(host='0.0.0.0', port=port)
