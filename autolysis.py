# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "seaborn",
#   "pandas",
#   "matplotlib",
#   "httpx",
#   "chardet",
#   "ipykernel",
#   "openai",
#   "numpy",
#   "scipy",
# ]
# ///

import os
import sys
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import httpx
import chardet
from pathlib import Path
import asyncio
import scipy.stats as stats
from PIL import Image
import numpy as np

# Ensure UTF-8 output for compatibility
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Constants
API_URL = "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"

# Helper Functions
def get_token():
    """Retrieve API token from environment variables."""
    try:
        return os.environ["AIPROXY_TOKEN"]
    except KeyError as e:
        print(f"Error: Environment variable '{e.args[0]}' not set.")
        raise

async def load_data(file_path):
    """Load CSV data with encoding detection."""
    file_path = Path(file_path)  # Ensure file_path is a Path object
    if not file_path.is_file():
        raise FileNotFoundError(f"Error: File '{file_path}' not found.")

    with open(file_path, 'rb') as f:
        result = chardet.detect(f.read())
    encoding = result['encoding']
    print(f"Detected file encoding: {encoding}")
    return pd.read_csv(file_path, encoding=encoding or 'utf-8')

async def analyze_data(df):
    """Perform detailed data analysis."""
    if df.empty:
        raise ValueError("Error: Dataset is empty.")

    summary_stats = df.describe(include='all').to_dict()
    missing_values = df.isnull().sum().to_dict()

    print("Summary Statistics:")
    print(summary_stats)

    print("Missing Values:")
    print(missing_values)

    return {
        'summary': summary_stats,
        'missing_values': missing_values
    }

async def visualize_data(df, output_dir):
    """Generate and save visualizations with smaller image size."""
    sns.set(style="whitegrid")
    numeric_columns = df.select_dtypes(include=['number']).columns

    output_dir.mkdir(parents=True, exist_ok=True)  # Create dataset-specific directory

    for column in numeric_columns:
        plt.figure(figsize=(8, 6))
        sns.histplot(df[column].dropna(), kde=True, color='cornflowerblue')
        plt.title(f'Distribution of {column}')
        plt.xlabel(column)
        plt.ylabel('Frequency')
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.savefig(output_dir / f"{column}_distribution.png", dpi=100)
        plt.close()

        # Resize images to 512x512 px for smaller size
        image_path = output_dir / f"{column}_distribution.png"
        img = Image.open(image_path)
        img = img.resize((512, 512))
        img.save(image_path)

    # Correlation Heatmap
    if len(numeric_columns) > 1:
        plt.figure(figsize=(10, 8))
        corr = df[numeric_columns].corr()
        sns.heatmap(corr, annot=True, cmap='viridis', square=True, cbar_kws={"shrink": 0.8})
        plt.title('Correlation Heatmap')
        plt.xticks(rotation=45)
        plt.yticks(rotation=45)
        heatmap_path = output_dir / "correlation_heatmap.png"
        plt.savefig(heatmap_path, dpi=100)
        plt.close()

        # Resize correlation heatmap
        img = Image.open(heatmap_path)
        img = img.resize((512, 512))
        img.save(heatmap_path)

    print("Visualizations saved to:", output_dir)

async def create_readme(analysis, output_dir):
    """Create README file with a brief narrative of the analysis."""
    narrative = f"# Data Analysis Report\n\n"
    narrative += f"## The Data You Received\n"
    narrative += f"The dataset consists of various numerical and categorical features, including columns such as {', '.join(analysis['summary'].keys())}.\n\n"

    narrative += f"## The Analysis You Carried Out\n"
    narrative += f"The analysis performed included the following steps:\n"
    narrative += "- Calculating summary statistics for each variable\n"
    narrative += "- Identifying missing values and the extent of data quality issues\n\n"

    narrative += f"## The Insights You Discovered\n"
    for column, stats in analysis['summary'].items():
        narrative += f"- **{column}**: Mean = {stats.get('mean', 'N/A')}, Std = {stats.get('std', 'N/A')}, Min = {stats.get('min', 'N/A')}, Max = {stats.get('max', 'N/A')}\n"

    for column, missing in analysis['missing_values'].items():
        narrative += f"- {column}: {missing} missing values\n"

    readme_path = output_dir / "README.md"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(narrative)

    print(f"README file created: {readme_path}")

async def main(file_path):
    try:
        file_path = Path(file_path)  # Ensure file_path is a Path object
        df = await load_data(file_path)

        # Dataset-specific output directory (same name as dataset)
        output_dir = Path(file_path.stem)
        output_dir.mkdir(parents=True, exist_ok=True)

        analysis = await analyze_data(df)
        await visualize_data(df, output_dir)
        await create_readme(analysis, output_dir)

        print(f"Analysis complete. Results saved to '{output_dir}'.")
    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        asyncio.run(main(sys.argv[1]))
    else:
        print("Usage: python autolysis.py <path_to_dataset>")
