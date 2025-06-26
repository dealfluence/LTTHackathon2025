document.addEventListener('DOMContentLoaded', () => {
    const userInput = document.getElementById('user-input');
    const userForm = document.getElementById('user-form');
    const userChatBox = document.getElementById('user-chat-box');

    const lawyerInput = document.getElementById('lawyer-input');
    const lawyerForm = document.getElementById('lawyer-form');
    const lawyerChatBox = document.getElementById('lawyer-chat-box');
    
    const status = document.getElementById('status');

    let ws;
    let lastUserMessageEl = null; // To track the last user message element for the reaction
    let reactionTimeout = null; // To control the timeout for showing the reaction

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
        // When Bob sends a message, clear any existing reaction
        clearReaction();
        
        if (data.type === 'user_response') {
            appendMessage(userChatBox, 'Bob', data.content, 'bob');
        } else if (data.type === 'lawyer_request') {
            appendMessage(lawyerChatBox, 'Bob', data.content, 'bob');
        }
    }

    function clearReaction() {
        if (reactionTimeout) {
            clearTimeout(reactionTimeout);
            reactionTimeout = null;
        }
        if (lastUserMessageEl) {
            const reaction = lastUserMessageEl.querySelector('.message-reaction');
            if (reaction) {
                reaction.remove();
            }
            lastUserMessageEl = null;
        }
    }

    function appendMessage(chatBox, sender, message, type) {
        const messageDiv = document.createElement('div');
        // Determine the correct class for alignment and styling
        const messageClass = type === 'human' ? 'message-human' : 'message-bob';
        // Combine structural classes with role-specific class
        messageDiv.className = `p-3 my-2 rounded message-container ${messageClass}`;
        
        const senderSpan = document.createElement('strong');
        senderSpan.textContent = sender;

        const messageP = document.createElement('p');
        messageP.className = 'mb-0';
        messageP.textContent = message;

        messageDiv.appendChild(senderSpan);
        messageDiv.appendChild(messageP);

        chatBox.appendChild(messageDiv);
        chatBox.scrollTop = chatBox.scrollHeight; // Auto-scroll
        
        return messageDiv; // Return the created element
    }

    userForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const message = userInput.value;
        if (message.trim() && ws.readyState === WebSocket.OPEN) {
            // Clear any previous reaction when a new message is sent
            clearReaction();

            const messageEl = appendMessage(userChatBox, 'User', message, 'human');
            lastUserMessageEl = messageEl; // Track this new message element

            // Set a timeout to add the "eyes" reaction
            reactionTimeout = setTimeout(() => {
                if (lastUserMessageEl) { // Check if it's still the last message
                    const reactionEl = document.createElement('div');
                    reactionEl.className = 'message-reaction';
                    reactionEl.textContent = '👀';
                    lastUserMessageEl.appendChild(reactionEl);
                }
            }, 1000); // 1-second delay

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