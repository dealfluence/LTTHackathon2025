let currentStatusElement = null;

function appendStatusMessage(chatBox, message) {
  const statusDiv = document.createElement("div");
  statusDiv.className = "status-message processing-dots";
  statusDiv.textContent = message;

  chatBox.appendChild(statusDiv);
  chatBox.scrollTop = chatBox.scrollHeight;

  return statusDiv;
}

function updateStatusMessage(statusElement, newMessage) {
  if (statusElement) {
    statusElement.textContent = newMessage;
    statusElement.className = "status-message processing-dots";
  }
}

function finalizeStatusMessage(statusElement, finalMessage) {
  if (statusElement) {
    statusElement.textContent = finalMessage;
    statusElement.className = "status-message"; // Remove processing-dots animation
  }
}

async function showStatusProgression(type) {
  const userChatBox = document.getElementById("user-chat-box");

  if (type === "user_processing") {
    // Clear any existing status
    if (currentStatusElement) {
      finalizeStatusMessage(
        currentStatusElement,
        currentStatusElement.textContent.replace(/\.\.\.$/, "")
      );
    }

    // State 1: Initial processing
    currentStatusElement = appendStatusMessage(
      userChatBox,
      "Bob is analyzing your question"
    );

    // State 2: Decision processing (after delay)
    await new Promise((resolve) => setTimeout(resolve, 800));
    updateStatusMessage(
      currentStatusElement,
      "Bob is checking if this requires review by our Legal Team"
    );
  } else if (type === "escalation") {
    // State 3B: Escalation
    await new Promise((resolve) => setTimeout(resolve, 600));
    updateStatusMessage(
      currentStatusElement,
      "Bob is consulting with our Legal Team"
    );
  } else if (type === "direct_response") {
    // State 3A: Direct response
    await new Promise((resolve) => setTimeout(resolve, 500));
    updateStatusMessage(currentStatusElement, "Bob is preparing your response");
  } else if (type === "contextual_analysis") {
    // Add this new case
    // State 4: Contextual analysis (for both direct and lawyer paths)
    await new Promise((resolve) => setTimeout(resolve, 400));
    updateStatusMessage(
      currentStatusElement,
      "Bob is checking for related contract information"
    );
  } else if (type === "lawyer_processing") {
    // State 4: Processing lawyer response
    currentStatusElement = appendStatusMessage(
      userChatBox,
      " incorporating our Legal Team's guidance into your response"
    );
  }
}
document.addEventListener("DOMContentLoaded", () => {
  const userInput = document.getElementById("user-input");
  const userForm = document.getElementById("user-form");
  const userChatBox = document.getElementById("user-chat-box");

  const lawyerInput = document.getElementById("lawyer-input");
  const lawyerForm = document.getElementById("lawyer-form");
  const lawyerChatBox = document.getElementById("lawyer-chat-box");

  const status = document.getElementById("status");

  let ws;
  let lastUserMessageEl = null; // To track the last user message element for the reaction
  let reactionTimeout = null; // To control the timeout for showing the reaction

  function connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onopen = () => {
      status.textContent = "Connected";
      status.className = "navbar-text text-success";
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleIncomingMessage(data);
    };

    ws.onclose = () => {
      status.textContent = "Disconnected. Retrying...";
      status.className = "navbar-text text-danger";
      setTimeout(connectWebSocket, 3000); // Retry connection after 3 seconds
    };

    ws.onerror = (error) => {
      console.error("WebSocket Error:", error);
      status.textContent = "Connection Error";
      status.className = "navbar-text text-danger";
      ws.close();
    };
  }

  function handleIncomingMessage(data) {
    // When Bob sends a message, clear any existing reaction
    clearReaction();

    if (data.type === "user_response") {
      // Finalize the current status before showing response
      if (currentStatusElement) {
        finalizeStatusMessage(
          currentStatusElement,
          currentStatusElement.textContent.replace(/\.\.\.$/, "")
        );
        currentStatusElement = null;
      }
      appendMessage(userChatBox, "Bob", data.content, "bob");
    } else if (data.type === "lawyer_request") {
      // Finalize status as "escalated" when lawyer request is sent
      if (currentStatusElement) {
        finalizeStatusMessage(
          currentStatusElement,
          "Bob consulted with legal counsel"
        );
        currentStatusElement = null;
      }
      appendMessage(lawyerChatBox, "Bob", data.content, "bob");
    } else if (data.type === "status_update") {
      // Handle status updates from backend
      if (data.status === "escalation") {
        showStatusProgression("escalation");
      } else if (data.status === "direct_response") {
        showStatusProgression("direct_response");
      } else if (data.status === "contextual_analysis") {
        // Add this new status
        showStatusProgression("contextual_analysis");
      }
    }
  }

  function clearReaction() {
    if (reactionTimeout) {
      clearTimeout(reactionTimeout);
      reactionTimeout = null;
    }
    if (lastUserMessageEl) {
      const reaction = lastUserMessageEl.querySelector(".message-reaction");
      if (reaction) {
        reaction.remove();
      }
      lastUserMessageEl = null;
    }
  }

  function appendMessage(chatBox, sender, message, type) {
    const isHuman = type === "human";

    // 1. Create the message bubble first, as it's always needed.
    const messageDiv = document.createElement("div");
    const messageClass = isHuman ? "message-human" : "message-bob";
    messageDiv.className = `p-3 rounded message-container ${messageClass}`;

    // 2. Populate the bubble with ONLY the message content.
    // The sender name is now handled outside or omitted.
    const messageP = document.createElement("p");
    messageP.className = "mb-0";
    messageP.textContent = message;
    messageDiv.appendChild(messageP);

    // 3. Decide what to append to the chatbox.
    let finalElementToAppend;
    if (isHuman) {
      // For humans, no sender name is shown. Just wrap for alignment.
      const row = document.createElement("div");
      row.className = "human-message-row";

      const bubbleContainer = document.createElement("div");
      bubbleContainer.className = "human-bubble-container";

      bubbleContainer.appendChild(messageDiv);
      row.appendChild(bubbleContainer);
      finalElementToAppend = row;
    } else {
      // For Bob, build the wrapper with avatar, name, and bubble.
      const wrapper = document.createElement("div");
      wrapper.className = "message-wrapper";

      // Avatar
      const avatar = document.createElement("div");
      avatar.className = "avatar";
      avatar.textContent = "B";

      // Container for name + bubble
      const bubbleAndNameContainer = document.createElement("div");
      bubbleAndNameContainer.className = "bubble-and-name-container";

      // Sender Name (styled, outside the bubble)
      const senderNameEl = document.createElement("div");
      senderNameEl.className = "sender-name";
      senderNameEl.textContent = sender; // e.g., "Bob"

      // Assemble the name and bubble vertically
      bubbleAndNameContainer.appendChild(senderNameEl);
      bubbleAndNameContainer.appendChild(messageDiv);

      // Assemble the final wrapper with avatar
      wrapper.appendChild(avatar);
      wrapper.appendChild(bubbleAndNameContainer);
      finalElementToAppend = wrapper;
    }

    chatBox.appendChild(finalElementToAppend);
    chatBox.scrollTop = chatBox.scrollHeight;

    // Return the message bubble itself for the reaction logic.
    return messageDiv;
  }

  userForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const message = userInput.value;
    if (message.trim() && ws.readyState === WebSocket.OPEN) {
      // Clear any previous reaction when a new message is sent
      clearReaction();

      const messageEl = appendMessage(userChatBox, "User", message, "human");
      lastUserMessageEl = messageEl; // Track this new message element

      // Set a timeout to add the "eyes" reaction
      reactionTimeout = setTimeout(() => {
        if (lastUserMessageEl) {
          // Check if it's still the last message
          const reactionEl = document.createElement("div");
          reactionEl.className = "message-reaction";
          reactionEl.textContent = "👀";
          lastUserMessageEl.appendChild(reactionEl);
        }
      }, 1000); // 1-second delay

      // Start status progression immediately
      showStatusProgression("user_processing");

      ws.send(JSON.stringify({ type: "user_message", content: message }));
      userInput.value = "";
    }
  });

  lawyerForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const message = lawyerInput.value;
    if (message.trim() && ws.readyState === WebSocket.OPEN) {
      appendMessage(lawyerChatBox, "Lawyer", message, "human");

      // Show processing status for lawyer response
      showStatusProgression("lawyer_processing");

      ws.send(JSON.stringify({ type: "lawyer_message", content: message }));
      lawyerInput.value = "";
    }
  });

  connectWebSocket();
});
