import json
import os
from typing import List, Dict, Any
from openai import OpenAI
import config

client = OpenAI(api_key=config.OPENAI_API_KEY)

def augment_tasks(sector: str, gold_tasks: List[Dict[str, Any]], num_new: int = 50) -> List[Dict[str, Any]]:
    """
    Use GPT-4o to generate new tasks similar to the gold ones for a sector.
    """
    augmented = []
    for task in gold_tasks:
        prompt = f"""
Based on this example task from the {sector} sector:
- Question: {task['question']}
- Reference Files: {task['reference_files']}
- Output: {task['output']}

Generate {num_new // len(gold_tasks)} new similar tasks. Each new task should include:
- A new question
- Similar reference files (vary slightly)
- A corresponding output

Format as a JSON list of dicts with keys: question, reference_files, output.
"""
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.7
            )
            new_tasks = json.loads(response.choices[0].message.content.strip())
            augmented.extend(new_tasks)
        except Exception as e:
            print(f"Error augmenting tasks for {sector}: {e}")
    return augmented[:num_new]  # Limit to num_new

def process_and_augment(gold_subset_path: str, output_dir: str) -> None:
    """
    Group gold tasks by sector, augment, and save per sector.
    Assumes gold_subset has 'sector' field or infer from occupation.
    """
    try:
        with open(gold_subset_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Gold subset file not found: {gold_subset_path}")
        return

    sectors = {}
    for item in data:
        sector = item.get('sector', 'unknown')  # Assume sector field
        if sector not in sectors:
            sectors[sector] = []
        sectors[sector].append(item)

    os.makedirs(output_dir, exist_ok=True)
    for sector, tasks in sectors.items():
        augmented = augment_tasks(sector, tasks, num_new=50)
        all_tasks = tasks + augmented
        output_path = os.path.join(output_dir, f"{sector.replace(' ', '_').lower()}_training.json")
        with open(output_path, 'w') as f:
            json.dump(all_tasks, f, indent=2)
        print(f"Augmented {sector} with {len(augmented)} tasks, total {len(all_tasks)} saved to {output_path}")

# Usage
if __name__ == "__main__":
    process_and_augment("gold_subset.json", "./council")