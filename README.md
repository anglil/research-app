# Research Manager App

A collaborative, graph-based tool for managing research projects, hypotheses, and evidence.

## Features
*   **Hypothesis Tree**: Visualize your research breakdown as an interactive tree or custom graph.
*   **Collaboration**: Real-time updates and "People View" to track contributions.
*   **Scalable**: Built on PostgreSQL to support 50+ concurrent users.
*   **Evidence Logs**: structured tracking of supporting/refuting evidence.

## Installation (Local)

To run this app locally on your machine:

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/anglil/research-app.git
    cd research-app
    ```

2.  **Install Dependencies**
    It is recommended to use a virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```

3.  **Run the App**
    ```bash
    streamlit run app.py
    ```
    *Note: By default, this will create a local SQLite database (`research_app.db`).*

## Deployment (Cloud)

This app is designed to be deployed on **Google Cloud Platform (Cloud Run)**.

See [gcp_deployment_guide.md](gcp_deployment_guide.md) for detailed instructions on how to deploy using the automated `setup_gcp.sh` script.

## Project Structure
*   `app.py`: Main Streamlit application.
*   `models_sql.py`: Database schema (SQLAlchemy).
*   `data_manager_sql.py`: Database CRUD operations.
*   `setup_gcp.sh`: Automated deployment script for GCP.
