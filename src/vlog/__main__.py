"""Entry point for running vlog.web as a module."""
import sys
import argparse
import os


def main():
    """Parse arguments and start the web server."""
    parser = argparse.ArgumentParser(description='Run the vlog web server')
    parser.add_argument('--port', type=int, default=5432, help='Port to run the server on (default: 5432)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Set environment variable for debug mode if specified
    if args.debug:
        os.environ['FLASK_DEBUG'] = 'true'
    
    # Import and run the app
    from vlog.web import app
    app.run(debug=args.debug, port=args.port)


if __name__ == '__main__':
    main()
