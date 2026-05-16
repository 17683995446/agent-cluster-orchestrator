#!/usr/bin/env python3
"""
File Watcher and Document Server for Architecture Documentation.

This script watches for file changes in the project and serves
the architecture documentation with auto-refresh capabilities.
"""
import os
import sys
import time
import threading
import logging
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Directories to watch
WATCH_DIRS = [
    '/workspace/backend/app',
    '/workspace/backend/app/api',
    '/workspace/backend/app/services',
    '/workspace/backend/app/models',
    '/workspace/ARCHITECTURE.md',
    '/workspace/README.md'
]

# File extensions to watch
WATCH_EXTENSIONS = {
    '.py', '.md', '.yml', '.yaml', '.json', '.toml',
    '.ts', '.tsx', '.js', '.jsx'
}

# Path to the architecture doc
DOC_PATH = Path('/workspace/docs/architecture.html')


def get_file_info(path):
    """Get file modification time and size."""
    try:
        stat = os.stat(path)
        return stat.st_mtime, stat.st_size
    except OSError:
        return None, None


def watch_files(callback):
    """Watch for file changes and call callback when changes detected."""
    file_cache = {}
    
    # Initialize cache
    for watch_path in WATCH_DIRS:
        if not os.path.exists(watch_path):
            continue
            
        if os.path.isfile(watch_path):
            mtime, size = get_file_info(watch_path)
            file_cache[watch_path] = (mtime, size)
        else:
            # Directory - walk recursively
            for root, dirs, files in os.walk(watch_path):
                for file in files:
                    if Path(file).suffix in WATCH_EXTENSIONS:
                        full_path = os.path.join(root, file)
                        mtime, size = get_file_info(full_path)
                        file_cache[full_path] = (mtime, size)
    
    logger.info(f'Watching {len(file_cache)} files for changes...')
    
    while True:
        changes = []
        
        # Check existing files
        for path, (old_mtime, old_size) in file_cache.copy().items():
            new_mtime, new_size = get_file_info(path)
            
            if new_mtime is None:
                changes.append(('deleted', path))
                del file_cache[path]
            elif new_mtime > old_mtime or new_size != old_size:
                changes.append(('modified', path))
                file_cache[path] = (new_mtime, new_size)
        
        # Check for new files
        for watch_path in WATCH_DIRS:
            if not os.path.exists(watch_path) or os.path.isfile(watch_path):
                continue
                
            for root, dirs, files in os.walk(watch_path):
                for file in files:
                    if Path(file).suffix in WATCH_EXTENSIONS:
                        full_path = os.path.join(root, file)
                        if full_path not in file_cache:
                            changes.append(('created', full_path))
                            mtime, size = get_file_info(full_path)
                            file_cache[full_path] = (mtime, size)
        
        if changes:
            logger.info(f'Detected {len(changes)} file change(s):')
            for change_type, path in changes:
                logger.info(f'  {change_type.upper()}: {path}')
            
            callback(changes)
        
        time.sleep(1)


def update_document(changes):
    """Update the architecture documentation timestamp."""
    if DOC_PATH.exists():
        # Read the file content
        with open(DOC_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update the timestamp in the file
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Just touch the file to update mtime
        os.utime(DOC_PATH)
        
        logger.info(f'Documentation updated at: {now}')
        logger.info('Refresh your browser to see changes!')


class CORSRequestHandler(SimpleHTTPRequestHandler):
    """HTTP request handler with CORS and custom headers."""
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()
    
    def log_message(self, format, *args):
        logger.info(f'{self.address_string()} - {format % args}')


def start_server(port=8080):
    """Start the HTTP server."""
    os.chdir('/workspace/docs')
    
    server_address = ('', port)
    httpd = HTTPServer(server_address, CORSRequestHandler)
    
    logger.info('=' * 60)
    logger.info(f'Architecture Documentation Server')
    logger.info('=' * 60)
    logger.info(f'Serving at: http://localhost:{port}/architecture.html')
    logger.info(f'Document path: {DOC_PATH}')
    logger.info('Watching for file changes...')
    logger.info('=' * 60)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info('Stopping server...')
        httpd.shutdown()


def main():
    """Main function to start watcher and server."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Architecture Documentation Server with file watching'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8080,
        help='Port to serve on (default: 8080)'
    )
    parser.add_argument(
        '--no-watch',
        action='store_true',
        help='Don\'t watch for file changes'
    )
    
    args = parser.parse_args()
    
    # Create docs directory if it doesn't exist
    DOC_PATH.parent.mkdir(exist_ok=True)
    
    if not args.no_watch:
        # Start file watcher in a separate thread
        watcher_thread = threading.Thread(
            target=watch_files,
            args=(update_document,),
            daemon=True
        )
        watcher_thread.start()
    
    # Start the server in the main thread
    start_server(args.port)


if __name__ == '__main__':
    main()
