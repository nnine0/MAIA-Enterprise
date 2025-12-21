import subprocess
import os
import requests
import config

def pull_thumbs_up_logs():
    from qdrant_client import QdrantClient
    client = QdrantClient(url="http://localhost:6333")  # Assuming local Qdrant
    # Query the "positive_interactions" collection for new logs since last update
    # For simplicity, scroll all and filter by timestamp or id
    results = client.scroll(collection_name="positive_interactions", limit=100)
    qa_pairs = []
    for point in results[0]:
        payload = point.payload
        qa_pairs.append({
            "query": payload.get("query"),
            "response": payload.get("response"),
            "context": payload.get("context", ""),
            "sector": payload.get("sector", "general")
        })
    return qa_pairs

def update_metadata(adapter_name, versioned_adapter):
    # Save to a JSON file
    import json
    metadata_file = "adapter_metadata.json"
    if os.path.exists(metadata_file):
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
    else:
        metadata = {}
    metadata[adapter_name] = versioned_adapter
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f)

def update_training_data(new_logs, output_file="maia_update.json"):
    # Format new logs into training data
    training_data = []
    for log in new_logs:
        training_data.append({
            "question": log["question"],
            "response": log["response"]
        })
    import json
    with open(output_file, 'w') as f:
        json.dump(training_data, f)
    return output_file

def run_training(adapter_name, dataset_path):
    # Version the adapter
    from datetime import datetime
    version = datetime.now().strftime("%Y%m%d_%H%M%S")
    versioned_adapter = f"{adapter_name}_v{version}"

    # Run train_expert.py with versioned name
    cmd = ["python", "train_expert.py"]
    env = os.environ.copy()
    env["ADAPTER_NAME"] = versioned_adapter
    env["DATASET_PATH"] = dataset_path
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode == 0:
        # Update metadata
        update_metadata(adapter_name, versioned_adapter)
        return True
    return False

def evaluate_adapter(adapter_name: str, golden_set: list) -> bool:
    if not golden_set:
        return True  # No golden set, pass

    import config
    general_adapter = "general"  # Assuming general is the judge

    scores = []
    for item in golden_set:
        # Generate response with the adapter
        response = requests.post(f"{config.LORAX_URL}/v1/chat/completions", json={
            "model": config.BASE_MODEL_ID,
            "messages": [
                {"role": "system", "content": f"You are an expert in {adapter_name}."},
                {"role": "user", "content": item["query"]}
            ],
            "extra_body": {"adapter_id": f"/adapters/{adapter_name}", "adapter_source": "local", "fallback_to_base": True}
        })
        if response.status_code != 200:
            return False
        generated = response.json()["choices"][0]["message"]["content"]

        # Have general adapter judge accuracy
        judge_prompt = f"Rate this response on a scale of 1-10 for accuracy and relevance to the query '{item['query']}'. Respond only with the number."
        judge_response = requests.post(f"{config.LORAX_URL}/v1/chat/completions", json={
            "model": config.BASE_MODEL_ID,
            "messages": [{"role": "user", "content": judge_prompt}],
            "extra_body": {"adapter_id": f"/adapters/{general_adapter}", "adapter_source": "local", "fallback_to_base": True}
        })
        if judge_response.status_code == 200:
            try:
                score = int(judge_response.json()["choices"][0]["message"]["content"].strip())
                scores.append(score)
            except ValueError:
                scores.append(5)  # Default
        else:
            scores.append(5)

    avg_score = sum(scores) / len(scores) if scores else 0
    print(f"Evaluation for {adapter_name}: Average score {avg_score:.2f} (threshold {config.EVALUATION_THRESHOLD})")
    return avg_score >= config.EVALUATION_THRESHOLD

def signal_lorax_refresh(adapter_name: str) -> bool:
    # First, evaluate
    golden_set = []  # Load golden set - TODO: implement loading from file or DB
    if not evaluate_adapter(adapter_name, golden_set):
        print(f"Evaluation failed for {adapter_name}, triggering rollback")
        # Trigger rollback via API
        maia_url = os.getenv("MAIA_URL", "http://maia-app:8000")
        rollback_response = requests.post(f"{maia_url}/rollback_adapter", json={"adapter_name": adapter_name})
        return False

    # Signal LoRAX to reload the adapter
    response = requests.post(f"{config.LORAX_URL}/adapters/refresh", json={"adapter_id": f"/adapters/{adapter_name}"})
    return response.status_code == 200

def weekend_update():
    # 1. Pull new logs
    new_logs = pull_thumbs_up_logs()
    if not new_logs:
        print("No new logs to update.")
        return

    # 2. Update training data
    dataset_path = update_training_data(new_logs)

    # 3. Run training for each adapter (or specific ones)
    adapters_to_update = ["general", "law", "finance"]  # Example
    for adapter in adapters_to_update:
        success = run_training(adapter, dataset_path)
        if success:
            signal_lorax_refresh(adapter)
            print(f"Updated adapter: {adapter}")
        else:
            print(f"Failed to update adapter: {adapter}")

if __name__ == "__main__":
    weekend_update()