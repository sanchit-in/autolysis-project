import os
import sys
import json
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
import requests
from dateutil.parser import parse

AIPROXY_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6IjIyZjMwMDMyODJAZHMuc3R1ZHkuaWl0bS5hYy5pbiJ9.aSGg9rbaDe1x6InI2_-n5acmwU6JEtIBCTbKm9IdgiU"
AI_PROXY_BASE_URL = "https://aiproxy.sanand.workers.dev/openai"

headers = {
    "Authorization": f"Bearer {AIPROXY_TOKEN}",
    "Content-Type": "application/json"
}

class AutoAnalysis:
    def __init__(self, csv_path):
        self.csv_path = csv_path
        self.df = pd.read_csv(csv_path, encoding='ISO-8859-1')
        self.plots = []
        self.dataset_name = os.path.splitext(os.path.basename(csv_path))[0].lower()
        self.output_dir = f"{self.dataset_name}"
        os.makedirs(self.output_dir, exist_ok=True)

    def query_llm(self, messages):
        url = f"{AI_PROXY_BASE_URL}/v1/chat/completions"
        data = {
            "model": "gpt-4o-mini",
            "messages": messages
        }
        response = requests.post(url, headers=headers, json=data)
        return response.json()

    def get_data_summary(self):
        desc_stats = self.df.describe(include='all').transpose()
        missing_values = self.df.isnull().sum()
        
        summary = {
            "num_rows": len(self.df),
            "num_columns": len(self.df.columns),
            "columns": self.df.columns.tolist(),
            "missing_values": missing_values.to_dict(),
            "desc_stats_summary": desc_stats.to_dict() if not desc_stats.empty else None,
            "sample_rows": self.df.head(3).to_dict('records')
        }
        return summary

    def create_plots(self, plot_type):
        if plot_type == "correlation":
            return self.create_correlation_heatmap()
        elif plot_type == "numeric":
            self.create_numeric_distributions()
        elif plot_type == "categorical":
            self.create_categorical_plots()
        elif plot_type == "clustering":
            return self.perform_clustering()

    def create_correlation_heatmap(self):
        numeric_data = self.df.select_dtypes(include=['number'])
        corr_matrix = numeric_data.corr() if not numeric_data.empty else None
        
        if corr_matrix is not None:
            plt.figure(figsize=(10, 8))
            sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap="coolwarm", center=0, cbar_kws={"shrink": 0.8})
            plt.title('Correlation Heatmap')
            plt.xticks(rotation=45)
            
            plot_path = os.path.join(self.output_dir, "correlation_heatmap.png")
            plt.savefig(plot_path, dpi=100)
            self.plots.append(plot_path)
            plt.close()
        
        return corr_matrix.to_dict() if corr_matrix is not None else None

    def create_numeric_distributions(self):
        numeric_columns = self.df.select_dtypes(include=['number']).columns

        for col in numeric_columns:
            if len(self.plots) >= 2:
                break
            
            plt.figure(figsize=(10, 6))
            sns.histplot(data=self.df, x=col, kde=True)
            plt.title(f"Distribution of {col}")
            plot_path = os.path.join(self.output_dir, f"{col}_distribution.png")
            plt.savefig(plot_path, dpi=100)
            self.plots.append(plot_path)
            plt.close()

    def create_categorical_plots(self):
        categorical_columns = self.df.select_dtypes(include=['object']).columns
        non_date_categoricals = [col for col in categorical_columns if not self.is_date_column(self.df[col])]

        unique_counts = {col: self.df[col].nunique() for col in non_date_categoricals}
        top_categorical_cols = sorted(unique_counts, key=unique_counts.get, reverse=True)[:2]

        for col in top_categorical_cols:
            if len(self.plots) >= 5:
                break
            
            top_categories = self.df[col].value_counts().head(10)
            plt.figure(figsize=(10, 6))
            sns.barplot(x=top_categories.index, y=top_categories.values)
            plt.title(f"Top 10 Categories in {col}")
            plt.xticks(rotation=45)
            
            plot_path = os.path.join(self.output_dir, f"{col}_top_categories.png")
            plt.savefig(plot_path, dpi=100)
            self.plots.append(plot_path)
            plt.close()

    def perform_clustering(self):
        numeric_df = self.df.select_dtypes(include=[np.number])
        numeric_df.dropna(inplace=True)
        if len(numeric_df) < 2:
            return None

        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(numeric_df)

        pca = PCA(n_components=2)
        reduced_features = pca.fit_transform(scaled_features)

        kmeans = KMeans(n_clusters=min(3, len(self.df)))
        clusters = kmeans.fit_predict(scaled_features)

        plt.figure(figsize=(10, 6))
        scatter = plt.scatter(reduced_features[:, 0], reduced_features[:, 1], c=clusters, cmap='viridis')
        plt.title('Data Clusters')
        plt.xlabel('First Principal Component')
        plt.ylabel('Second Principal Component')
        plt.colorbar(scatter)
        plot_path = os.path.join(self.output_dir, 'clusters.png')
        plt.savefig(plot_path, dpi=100, bbox_inches='tight')
        self.plots.append(plot_path)
        plt.close()

        return {
            "n_clusters": len(np.unique(clusters)),
            "cluster_sizes": pd.Series(clusters).value_counts().to_dict()
        }

    def is_date_column(self, series):
        if series.dtype == 'datetime64[ns]':
            return True
        if series.dtype == 'object':
            try:
                sample = series.dropna().sample(min(10, len(series.dropna())))
                for value in sample:
                    parse(value, fuzzy=False)
                return True
            except (ValueError, TypeError):
                return False
        return False

    def analyze_and_visualize(self):
        data_summary = self.get_data_summary()
        
        messages = [{
            "role": "system",
            "content": "You are a data analysis expert. Given a dataset summary, suggest specific analyses to perform."
        }, {
            "role": "user",
            "content": f"Here's my dataset summary: {json.dumps(data_summary, indent=2)}\nWhat analyses should I perform?"
        }]
        
        response = self.query_llm(messages)
        
        if 'choices' not in response:
            print(f"API request failed. Full response: {response}")
            sys.exit(1)
        
        analysis_plan = response['choices'][0]['message']['content']
        
        correlation_data = self.create_plots("correlation")
        self.create_plots("numeric")
        clustering_results = self.create_plots("clustering")
        self.create_plots("categorical")
        
        analysis_results = {
            "data_summary": data_summary,
            "correlation_data": correlation_data,
            "clustering_results": clustering_results
        }
        
        messages = [{
            "role": "system",
            "content": "You are a data storyteller. Create a markdown report with insights from the analysis."
        }, {
            "role": "user",
            "content": f"""Please create a README.md with these sections:
            1. Data Overview
            2. Analysis Performed
            3. Key Insights
            4. Implications
            
            Here's the analysis data: {json.dumps(analysis_results, indent=2)}
            
            Include these images in order:
            {', '.join(self.plots)}
            
            Make sure to:
            - Use proper markdown formatting
            - Reference the images correctly
            - Focus on actionable insights
            - Keep it concise but informative"""
        }]
        
        response = self.query_llm(messages)
        
        if 'choices' not in response:
            print(f"API request failed. Full response: {response}")
            sys.exit(1)
        
        readme_content = response['choices'][0]['message']['content']
        
        with open(os.path.join(self.output_dir, 'README.md'), 'w') as f:
            f.write(readme_content)

def main():
    if len(sys.argv) != 2:
        print("Usage: python autolysis.py <csv_file>")
        sys.exit(1)
        
    csv_path = sys.argv[1]
    if not os.path.exists(csv_path):
        print(f"Error: File {csv_path} not found")
        sys.exit(1)
        
    analyzer = AutoAnalysis(csv_path)
    analyzer.analyze_and_visualize()

if __name__ == "__main__":
    main()
