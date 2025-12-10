from crewai.tools import tool
from .clip_retriever import EmergencyImageRetriever

# Initialize CLIP retriever (singleton for efficiency)
_retriever = None

def get_retriever():
    """Get or initialize the CLIP retriever singleton"""
    global _retriever
    if _retriever is None:
        _retriever = EmergencyImageRetriever()
    return _retriever


@tool("Search Emergency Image Database")
def search_emergency_image(query: str) -> str:
    """
    Search for the most relevant emergency medical instruction image based on the query.
    Use this tool to find visual guidance for emergency situations like CPR, choking, 
    recovery position, etc.
    
    Args:
        query: A description of the emergency situation (e.g., "baby choking", 
               "adult CPR", "pregnant woman choking", "unconscious person breathing")
    
    Returns:
        Information about the best matching image including filename, category, 
        description, and relevance score.
    """
    try:
        retriever = get_retriever()
        results = retriever.retrieve(query, top_k=1)
        
        if results:
            best_match = results[0]
            # Normalize similarity score (boosted scores can exceed 1.0)
            raw_similarity = best_match['similarity']
            # Clamp to reasonable range and convert to percentage
            relevance_pct = min(max(raw_similarity, 0), 2.5) / 2.5 * 100
            
            # Warn if relevance is low
            relevance_warning = ""
            if relevance_pct < 40:
                relevance_warning = """
⚠️ ATTENTION: Cette image peut ne pas correspondre parfaitement à la situation.
   Considère de NE PAS inclure cette image ou cherche avec d'autres mots-clés.
"""
            
            return f"""
═══════════════════════════════════════════════════════════════════
📷 IMAGE TROUVÉE
═══════════════════════════════════════════════════════════════════
{relevance_warning}
📁 CHEMIN IMAGE (à copier tel quel) :
{best_match['filename']}

📂 CATÉGORIE : {best_match['category']} - {best_match['subcategory']}

📝 CE QUE MONTRE L'IMAGE (à décrire dans ta réponse) :
{best_match['caption']}

🏷️ MOTS-CLÉS : {', '.join(best_match['keywords'][:8])}

📊 PERTINENCE : {relevance_pct:.0f}%

═══════════════════════════════════════════════════════════════════
⚠️ INSTRUCTIONS OBLIGATOIRES :
═══════════════════════════════════════════════════════════════════
Quand tu utilises cette image dans ta réponse :
1. COPIE le chemin EXACT ci-dessus
2. DÉCRIS ce que montre l'image en utilisant la description ci-dessus

FORMAT À UTILISER :
📷 GUIDE VISUEL : [chemin image]
Cette image montre : [description de ce que montre l'image]
═══════════════════════════════════════════════════════════════════
"""
        return "❌ Aucune image correspondante trouvée. Ne mentionne pas d'image dans ta réponse."
    except Exception as e:
        return f"❌ Erreur lors de la recherche d'image: {str(e)}. Continue sans image."


@tool("Browse Emergency Categories")
def browse_emergency_categories(category: str) -> str:
    """
    Browse all images available in a specific emergency category.
    Use this tool when you want to see all available images for a category
    rather than searching for a specific situation.
    
    Args:
        category: The category to browse. Available categories are:
                  - "CPR" (includes adult and infant)
                  - "Choking" (includes adult, child, infant, pregnant)
                  - "Recovery Position"
                  - "Log Roll" (turning casualty face up)
    
    Returns:
        A list of all images in the specified category with their descriptions.
    """
    retriever = get_retriever()
    
    # Map user-friendly names to actual category names
    category_map = {
        'cpr': 'CPR',
        'choking': 'First aid for choking',
        'recovery': 'Recovery Position',
        'recovery position': 'Recovery Position',
        'log roll': 'How to turn a casualty face up',
        'turn casualty': 'How to turn a casualty face up'
    }
    
    mapped_category = category_map.get(category.lower(), category)
    images = retriever.search_by_category(mapped_category)
    
    if not images:
        # Try partial match
        for img in retriever.metadata:
            if category.lower() in img['category'].lower():
                images.append(img)
    
    if images:
        result = f"📁 Found {len(images)} images in '{mapped_category}':\n\n"
        for i, img in enumerate(images, 1):
            result += f"{i}. {img['filename']}\n"
            result += f"   Subcategory: {img['subcategory']}\n"
            result += f"   Description: {img['caption']}\n\n"
        return result
    
    return f"No images found in category '{category}'. Available categories: CPR, Choking, Recovery Position, Log Roll"

