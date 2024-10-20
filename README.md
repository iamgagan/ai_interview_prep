# AI Interview Prep Application

## Description

The AI Interview Prep Application is an innovative tool designed to help job seekers practice and improve their interviewing skills. Utilizing advanced AI technology, this application simulates a real interview experience, providing users with industry-specific questions and immediate feedback on their responses.

## Features

- Customizable interview scenarios based on job position, industry, and specialization
- Support for both text and voice input for responses
- Real-time speech-to-text conversion for voice inputs
- AI-generated questions tailored to the user's chosen field
- Immediate feedback and evaluation of responses
- Option to end the interview at any time and receive an overall evaluation
- Seamless conversation flow with natural follow-up questions

## Prerequisites

Before you begin, ensure you have met the following requirements:

- Python 3.7 or higher
- An OpenAI API key

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/ai_interview_prep.git
   ```

2. Navigate to the project directory:
   ```
   cd ai_interview_prep
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up your OpenAI API key as an environment variable:
   ```
   export OPENAI_API_KEY='your-api-key-here'
   ```

## Usage

To start the AI Interview Prep Application, run the following command in your terminal:

```
python main.py
```

Follow the on-screen prompts to set up your interview:

1. Enter your job position
2. Select your industry
3. If applicable, choose your industry coverage and vertical
4. Provide a job description
5. Upload your CV (ensure it's in PDF format)

During the interview:

- Choose between text or voice input for each response
- For text input, type 'done' on a new line when you've finished your answer
- For voice input, press Enter to start and stop recording
- Type 'quit' at any time to end the interview and receive your evaluation

## Configuration

You can modify the following parameters in the `AIInterviewPrep` class:

- `self.industries`: List of available industries
- `self.blue_industries`: Industries with specialized coverage options
- `self.industry_coverage_options`: Available industry coverage options
- `self.orange_options`: Industries with vertical specializations
- `self.verticals`: Available vertical specializations

## Contributing

Contributions to the AI Interview Prep Application are welcome. Please follow these steps:

1. Fork the repository
2. Create a new branch: `git checkout -b <branch_name>`
3. Make your changes and commit them: `git commit -m '<commit_message>'`
4. Push to the original branch: `git push origin <project_name>/<location>`
5. Create the pull request

Alternatively, see the GitHub documentation on [creating a pull request](https://help.github.com/articles/creating-a-pull-request/).

## License

This project uses the following license: [MIT License](https://opensource.org/licenses/MIT).

## Contact

If you want to contact me, you can reach me at `<your_email@example.com>`.

## Acknowledgements

- OpenAI for providing the GPT model used in this application
- The SpeechRecognition library for enabling voice input functionality
