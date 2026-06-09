import os
from typing import Dict, Any

def search_data_store(project_id: str, location: str, data_store_id: str, search_query: str) -> str:
    """
    Search Google Cloud Agent Builder (Vertex AI Search) Data Store.
    This fulfills the hackathon requirement to use Google Cloud Agent Builder at runtime.
    """
    try:
        from google.cloud import discoveryengine_v1 as discoveryengine
        
        client = discoveryengine.SearchServiceClient()
        serving_config = client.serving_config_path(
            project=project_id,
            location=location,
            data_store=data_store_id,
            serving_config="default_config",
        )

        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=search_query,
            page_size=3,
        )

        response = client.search(request)
        
        results_text = []
        for result in response.results:
            doc_data = result.document.derived_struct_data
            
            # Try to get extractive answers or snippets
            snippet = ""
            if "extractive_answers" in doc_data and doc_data["extractive_answers"]:
                snippet = doc_data["extractive_answers"][0].get("content", "")
            elif "snippets" in doc_data and doc_data["snippets"]:
                snippet = doc_data["snippets"][0].get("snippet", "")
            
            if snippet:
                results_text.append(snippet)
                
        if not results_text:
            return "No relevant information found in the Google Cloud Agent Builder Data Store."
            
        return "Google Cloud Agent Builder Results:\n" + "\n\n".join(results_text)
        
    except ImportError:
        return "Error: google-cloud-discoveryengine library is not installed."
    except Exception as e:
        return f"Error querying Agent Builder: {str(e)}"
