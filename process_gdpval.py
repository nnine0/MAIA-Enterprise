import json
import os
from typing import List, Dict, Any
from openai import OpenAI
import config

# Initialize OpenAI client
client = OpenAI(api_key=config.OPENAI_API_KEY)

def synthesize_cot(question: str, reference_files: Any, final_output: str) -> str:
    """
    Use GPT-4o to back-solve the reasoning steps.
    """
    prompt = f"""
Given the following:
- Question/Task: {question}
- Reference Files/Content: {reference_files}
- Final Expert Output: {final_output}

Write the step-by-step logical 'thinking' process that leads from the reference files to this perfect output. Format as a coherent chain-of-thought reasoning.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.5
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error synthesizing CoT for question: {question[:50]}...: {e}")
        return "Error in synthesis."

def process_gdpval_gold_subset(gold_subset_path: str, output_path: str) -> None:
    """
    Process the GDPval Gold Subset JSON to generate training data with CoT.
    Assumes gold_subset is a list of dicts with 'question', 'reference_files', 'output'
    """
    try:
        with open(gold_subset_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Gold subset file not found: {gold_subset_path}")
        return

    training_data = []
    for item in data:
        question = item.get('question', '')
        reference_files = item.get('reference_files', '')
        final_output = item.get('output', '')

        cot = synthesize_cot(question, reference_files, final_output)

        # Format for training
        training_pair = {
            "question": question,
            "response": f"<thinking>\n{cot}\n</thinking>\n{final_output}"
        }
        training_data.append(training_pair)

    with open(output_path, 'w') as f:
        json.dump(training_data, f, indent=2)

    print(f"Processed {len(training_data)} items into {output_path}")

# Usage
if __name__ == "__main__":
    # Download gold_subset.json from evals.openai.com first
    process_gdpval_gold_subset("gold_subset.json", "gdpval_training_data.json")