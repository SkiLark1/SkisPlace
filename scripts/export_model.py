import torch
from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor
import os

# Configuration
MODEL_NAME = "nvidia/segformer-b0-finetuned-ade-512-512"
OUTPUT_PATH = "services/api/models/model.onnx"

def main():
    print(f"Downloading {MODEL_NAME}...")
    try:
        model = SegformerForSemanticSegmentation.from_pretrained(MODEL_NAME)
        model.eval()
    except Exception as e:
        print(f"Error loading model. Do you have 'transformers' installed? pip install transformers torch")
        raise e

    # Create dummy input (Batch, Channel, Height, Width)
    dummy_input = torch.randn(1, 3, 512, 512)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    print(f"Exporting to ONNX at {OUTPUT_PATH}...")
    torch.onnx.export(
        model, 
        dummy_input, 
        OUTPUT_PATH,
        opset_version=11,
        input_names=['input'], 
        output_names=['output'],
        dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}}
    )
    print("Export complete!")

if __name__ == "__main__":
    main()
