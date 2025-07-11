# LinkedIn People Connection Bot

A Python automation tool that helps you connect with people on LinkedIn by sending personalized connection requests with custom messages.

## Features

- 🚀 **Automated Connection Requests**: Automatically sends connection requests to profiles with "Connect" buttons
- 📝 **Personalized Messages**: Customizable message template with name extraction for personalization
- 🏃‍♂️ **Quick Connection Mode**: Option to send connection requests without a note for faster processing
- 🛡️ **Invitation Limit Protection**: Automatically detects and handles LinkedIn's invitation limits
- 👥 **Follow Automation**: Also follows profiles that have "Follow" buttons
- 🔄 **Multi-page Navigation**: Processes multiple pages of search results automatically
- 🔙 **Bidirectional Navigation**: Can navigate both forward and backward through search results
- 🎯 **Smart Targeting**: Works with LinkedIn search results to target specific profiles
- ⚡ **Existing Browser Support**: Can work with your already-opened LinkedIn session

## Prerequisites

- Python 3.7+
- Chrome browser
- ChromeDriver (automatically managed by selenium)
- Active LinkedIn account

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/linkedin-people-connection-bot.git
cd linkedin-people-connection-bot
```

2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Method 1: Using Existing Browser Session (Recommended)

1. **Open Chrome with debugging enabled**:
```bash
# On macOS/Linux:
google-chrome --remote-debugging-port=9222 --user-data-dir="$(mktemp -d)"

# On Windows:
chrome.exe --remote-debugging-port=9222 --user-data-dir="%TEMP%\chrome_debug"
```

2. **Navigate to LinkedIn** in the opened browser and log in

3. **Perform your search** (e.g., search for "tech recruiter", "software engineer", or any other professionals you want to connect with)

4. **Run the automation**:
```bash
python main.py
```

### Method 2: Fresh Browser Session

Simply run the script without the debugging setup:
```bash
python main.py
```

The script will open a new Chrome window where you'll need to manually log in and navigate to your search results.

## Command Line Options

- `-y`, `--yes`: Automatically continue past "close to limit" warnings (will still stop at hard limit)
- `-m`, `--message`: Path to message template file (default: message.txt)
- `-r`, `--reverse`: Navigate in reverse (use Previous button instead of Next)
- `-n`, `--no-message`: Send invitations without a note (faster processing)

Examples:
```bash
python main.py -y
python main.py -m custom_message.txt
python main.py -r  # Navigate in reverse (from newest to oldest search results)
python main.py -n  # Send connection requests without a note
python main.py -y -m my_template.txt -r
python main.py -y -n -r  # Auto-continue, no notes, reverse navigation
```

## Message Customization

The message template is loaded from `message.txt` and can be customized by editing this file:

```
Olá, {name}!
Sou Full Stack Developer focado em backend com 5+ anos de experiência, sendo os últimos 3 anos em Java Spring & React. Apaixonado por café, simplificar problemas complexos e entregar soluções robustas.
Espero que meu perfil desperte seu interesse!
```

### Template Features:
- **Name Personalization**: Use `{name}` anywhere in the message to insert the recipient's first name
- **Character Limit**: Messages are automatically truncated to 300 characters (LinkedIn's limit)
- **Fallback**: If name extraction fails, `{name}` is replaced with an empty string

### Examples:
- `"Hello {name}!"` → `"Hello John!"`
- `"Hi {name}, hope you're doing well!"` → `"Hi Sarah, hope you're doing well!"`
- If name not found: `"Hello {name}!"` → `"Hello !"`

## Safety Features

### Invitation Limit Protection
- **Soft Warning**: When close to weekly limit, asks for user confirmation (unless `-y` flag is used)
- **Hard Limit**: Automatically stops when weekly invitation limit is reached
- **Verification**: Confirms each invitation was sent successfully before proceeding

### Human-like Behavior
- Random delays between actions (1-5 seconds)
- Scrolling to elements before clicking
- JavaScript-based clicking to avoid detection

## How It Works

1. **Page Processing**: Scans the current page for "Connect" buttons
2. **Name Extraction**: Attempts to extract the recipient's name from their profile
3. **Connection Request**:
   - With notes: Clicks "Connect" → "Add a note" → fills personalized message → sends
   - Without notes: Clicks "Connect" → "Send without a note" (when `-n` flag is used)
4. **Following**: Clicks any "Follow" buttons on the page
5. **Navigation**: Moves to the next page (or previous page with `-r` flag) of results
6. **Repeat**: Continues until all pages are processed or limits are reached

## Best Practices

1. **Use Conservative Limits**: Don't exceed LinkedIn's weekly invitation limits
2. **Personalize Messages**: Customize the message template for your specific use case
3. **Target Specifically**: Use LinkedIn's search filters to target relevant profiles
4. **Monitor Usage**: Keep track of your weekly invitation count
5. **Respect LinkedIn's Terms**: Use this tool responsibly and in accordance with LinkedIn's terms of service

## Troubleshooting

### Common Issues

1. **ChromeDriver Issues**:
   - Ensure Chrome browser is installed
   - The script uses selenium's built-in ChromeDriver management

2. **Connection Failures**:
   - Check your internet connection
   - Verify you're logged into LinkedIn
   - Ensure the search results page is loaded

3. **Element Not Found**:
   - LinkedIn's UI may have changed
   - Try refreshing the page and running again

### Debug Mode

Add print statements or modify the logging to see what's happening:
```python
print(f"Processing button {i+1}: {button.text}")
```

## Limitations

- LinkedIn limits invitations to ~100 per week for free accounts
- The script works with LinkedIn's current UI (subject to change)
- May not work with all LinkedIn page layouts
- Designed for desktop LinkedIn interface

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Disclaimer

This tool is for educational and personal use only. Users are responsible for complying with LinkedIn's Terms of Service and applicable laws. The authors are not responsible for any misuse or consequences resulting from the use of this tool.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

If you encounter issues or have questions, please open an issue on GitHub.