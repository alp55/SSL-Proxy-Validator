# SSL Proxy Validator

A specialized Python tool designed to identify and validate proxies that support SSL/HTTPS connections. This tool helps you find and verify secure proxies that can handle encrypted traffic efficiently.

## Features

- Multi-threaded proxy testing
- Support for HTTP/HTTPS proxies
- Automatic retry mechanism
- Real-time testing statistics
- CSV file support for proxy lists
- Split testing capability for large proxy lists
- Keyboard interrupt handling
- Response time measurement
- URL management system
- Automated test result saving

## Requirements

- Python 3.x
- Required Python packages:
  - selenium
  - requests
  - pynput
  - urllib3
  - socks

## Installation

1. Clone the repository:
```bash
git clone https://github.com/alp55/proxy-tester.git
cd proxy-tester
```

2. Install required packages:
```bash
pip install selenium requests pynput urllib3 pysocks
```

## Usage

The tool offers several operating modes:

1. Load Proxy List from URL
2. Load Proxy List from File
3. Test Proxies from CSV
4. Automatic Split Testing
5. Combine Part Files

To run the tool:
```bash
python proxy_tester.py
```

## Features in Detail

### URL-based Proxy Loading
- Supports loading proxy lists from URLs
- Saves frequently used URLs for quick access
- Automatic URL validation

### File-based Operations
- CSV file support for storing working proxies
- Automatic file management for split testing
- Result combination functionality

### Testing Capabilities
- Connection timeout checking
- SSL verification
- Response time measurement
- Proxy protocol detection
- Duplicate removal
- Sorting by response time

### Real-time Monitoring
- Live statistics display
- Progress tracking
- Keyboard interrupt support ('s' key to stop)
- Detailed error reporting

## Output Format

The tool saves working proxies in CSV format with the following columns:
- IP
- Port
- Protocol
- Timeout (response time in ms)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Author

**Alperen Ulutas**
- GitHub: [@alp55](https://github.com/alp55)
- Email: alperen.ulutas.1@gmail.com

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Thanks to all contributors who have helped with testing and improvements
- Special thanks to the Python community for the excellent libraries that made this project possible