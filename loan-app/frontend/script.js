document.getElementById('loanForm').addEventListener('submit', async (e) => {
    e.preventDefault();
  
    const applicant = {
      name: document.getElementById('name').value,
      age: parseInt(document.getElementById('age').value),
      creditScore: parseInt(document.getElementById('creditScore').value),
      income: parseInt(document.getElementById('income').value),
      employmentStatus: document.getElementById('employmentStatus').value,
    };
  
    const response = await fetch('http://localhost:5000/check-eligibility', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(applicant),
    });
  
    const result = await response.json();
    const eligibilityResult = document.getElementById('eligibilityResult');
    eligibilityResult.innerHTML = result.eligible
      ? `<strong>Congratulations!</strong> You are eligible for the loan.<br>Reason: ${result.reason}`
      : `<strong>Sorry,</strong> you are not eligible for the loan.<br>Reason: ${result.reason}`;
  });
  
  document.getElementById('chatForm').addEventListener('submit', async (e) => {
    e.preventDefault();
  
    const chatInput = document.getElementById('chatInput');
    const chatMessages = document.getElementById('chatMessages');
  
    const userMessage = document.createElement('div');
    userMessage.textContent = `You: ${chatInput.value}`;
    chatMessages.appendChild(userMessage);
  
    const response = await fetch('http://localhost:5000/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message: chatInput.value }),
    });
  
    const data = await response.json();
    const assistantMessage = document.createElement('div');
    assistantMessage.textContent = `Assistant: ${data.response}`;
    chatMessages.appendChild(assistantMessage);
  
    chatInput.value = '';
    chatMessages.scrollTop = chatMessages.scrollHeight;
  });