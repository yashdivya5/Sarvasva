import fetch from 'node-fetch';
import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';

dotenv.config(); // Load environment variables from .env file

const app = express();
const port = 5000;

// Middleware
app.use(cors());
app.use(express.json());

// Route to check loan eligibility using DeepSeek API
app.post('/check-eligibility', async (req, res) => {
  const applicant = req.body;

  try {
    // Prepare the prompt for the AI model
    const prompt = `
      Analyze the following applicant details and determine if they are eligible for a loan:
      - Name: ${applicant.name}
      - Age: ${applicant.age}
      - Credit Score: ${applicant.creditScore}
      - Annual Income: ${applicant.income}
      - Employment Status: ${applicant.employmentStatus}

      Eligibility Criteria:
      - Age must be between 21 and 65.
      - Credit Score must be 650 or higher.
      - Annual Income must be at least $25,000.
      - Employment Status must be "employed" or "self-employed".

      Provide a response in the following JSON format:
      {
        "eligible": true/false,
        "reason": "Brief explanation of the decision"
      }
    `;

    // Call the DeepSeek API
    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${process.env.DEEPSEEK_API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        "model": "openai/gpt-3.5-turbo", // Use any supported model
        "messages": [
          {
            "role": "user",
            "content": prompt
          }
        ]
      })
    });

    const data = await response.json();
    const eligibilityResult = JSON.parse(data.choices[0].message.content);

    res.json(eligibilityResult);
  } catch (error) {
    console.error("Error fetching response:", error.message);
    res.status(500).json({ error: "Something went wrong. Please try again." });
  }
});

// Route to interact with the chatbot
app.post('/chat', async (req, res) => {
  const { message } = req.body;

  try {
    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${process.env.DEEPSEEK_API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        "model": "openai/gpt-3.5-turbo",
        "messages": [
          {
            "role": "user",
            "content": message
          }
        ]
      })
    });

    const data = await response.json();
    res.json({ response: data.choices[0].message.content });
  } catch (error) {
    console.error("Error fetching response:", error.message);
    res.status(500).json({ error: "Something went wrong. Please try again." });
  }
});

// Start the server
app.listen(port, () => {
  console.log(`Server is running on http://localhost:${port}`);
});