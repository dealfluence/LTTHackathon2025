// FILE: static/js/main.js
document.addEventListener('DOMContentLoaded', () => {
    const userInput = document.getElementById('user-input');
    const userForm = document.getElementById('user-form');
    const userChatBox = document.getElementById('user-chat-box');

    const lawyerInput = document.getElementById('lawyer-input');
    const lawyerForm = document.getElementById('lawyer-form');
    const lawyerChatBox = document.getElementById('lawyer-chat-box');
    
    const status = document.getElementById('status');

    let ws;

    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

        ws.onopen = () => {
            status.textContent = 'Connected';
            status.className = 'navbar-text text-success';
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleIncomingMessage(data);
        };

        ws.onclose = () => {
            status.textContent = 'Disconnected. Retrying...';
            status.className = 'navbar-text text-danger';
            setTimeout(connectWebSocket, 3000); // Retry connection after 3 seconds
        };

        ws.onerror = (error) => {
            console.error('WebSocket Error:', error);
            status.textContent = 'Connection Error';
            status.className = 'navbar-text text-danger';
            ws.close();
        };
    }
    
    function handleIncomingMessage(data) {
        if (data.type === 'user_response') {
            appendMessage(userChatBox, 'Bob', data.content, 'bob');
        } else if (data.type === 'lawyer_request') {
            appendMessage(lawyerChatBox, 'Bob', data.content, 'bob');
        }
    }

    function appendMessage(chatBox, sender, message, type) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `p-2 my-2 rounded ${type === 'human' ? 'bg-primary bg-opacity-10' : 'bg-secondary bg-opacity-10'}`;
        
        const senderSpan = document.createElement('strong');
        senderSpan.textContent = sender;

        const messageP = document.createElement('p');
        messageP.className = 'mb-0';
        messageP.textContent = message;

        messageDiv.appendChild(senderSpan);
        messageDiv.appendChild(messageP);

        chatBox.appendChild(messageDiv);
        chatBox.scrollTop = chatBox.scrollHeight; // Auto-scroll
    }

    userForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const message = userInput.value;
        if (message.trim() && ws.readyState === WebSocket.OPEN) {
            appendMessage(userChatBox, 'User', message, 'human');
            ws.send(JSON.stringify({ type: 'user_message', content: message }));
            userInput.value = '';
        }
    });
    
    lawyerForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const message = lawyerInput.value;
        if (message.trim() && ws.readyState === WebSocket.OPEN) {
            appendMessage(lawyerChatBox, 'Lawyer', message, 'human');
            ws.send(JSON.stringify({ type: 'lawyer_message', content: message }));
            lawyerInput.value = '';
        }
    });

    connectWebSocket();
});