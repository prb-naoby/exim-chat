# EXIM Chatbot Application

A Streamlit application with credential-based login and two specialized chatbots for EXIM operations.

## Features

- 🔐 Credential-based login system
- 📋 INSW Chatbot - Search INSW regulations from INTR website
- 📖 SOP Chatbot - Answer questions about EXIM department SOPs
- 📱 Sidebar navigation
- 💬 Independent chat histories for each chatbot
- 🚪 Logout functionality

## Installation

1. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

1. Run the application:
```bash
streamlit run app.py
```

2. Login with one of the demo credentials:
   - Username: `admin`, Password: `admin123`
   - Username: `user`, Password: `user123`

3. Navigate between the two chatbot pages using the sidebar:
   - **INSW Chatbot** - Search for INSW regulations from INTR website
   - **SOP Chatbot** - Get information about EXIM department SOPs

## Project Structure

```
.
├── app.py                    # Main application with login and navigation
├── modules/
│   ├── __init__.py          # Package initializer
│   ├── insw_chatbot.py      # INSW Chatbot - INSW regulation search
│   └── sop_chatbot.py       # SOP Chatbot - EXIM department SOPs
├── requirements.txt          # Python dependencies
└── README.md                # This file
```

## Customization

### INSW Chatbot (modules/insw_chatbot.py)
- Replace `search_insw_regulation()` function with actual INTR website integration
- Implement web scraping or API calls to fetch INSW regulations
- Add document parsing and search capabilities

### SOP Chatbot (modules/sop_chatbot.py)
- Replace `search_sop_exim()` function with actual SOP database/document search
- Implement vector database or document retrieval system
- Add SOP document parsing and Q&A capabilities

### Security
- Update the credentials in `app.py` (use proper authentication in production)
- Add more features like file uploads, document attachments, etc.

## Security Note

⚠️ The current authentication is for demonstration purposes only. In a production environment, you should:
- Use proper password hashing
- Store credentials securely (e.g., database, environment variables)
- Implement proper session management
- Add HTTPS support
- Consider using OAuth or other secure authentication methods
