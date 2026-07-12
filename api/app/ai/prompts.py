"""Production prompts (spec Appendix B). All demand ONLY minified JSON."""

VISION_SYSTEM = (
    "You extract structured signals from a shared image (usually a screenshot of a web page). "
    'Return ONLY minified JSON of the form: '
    '{"detected_service":<enum>,"visible_url":<string|null>,"title_guess":<string|null>,'
    '"ocr_text":<string>,"candidate_entities":[{"type":<string>,"value":<string>}]} '
    'detected_service must be one of ["github","imdb","movie","youtube","twitter","product",'
    '"recipe","article","generic"]. '
    "Base detected_service on logos, the address bar, and layout - not only on text. "
    'If you cannot tell, use "generic" and leave candidate_entities empty. '
    "Never output prose, markdown, or explanations.\n\n"
    "Example 1 - the github.com/facebook/react repository page:\n"
    '{"detected_service":"github","visible_url":"github.com/facebook/react",'
    '"title_guess":"facebook/react","ocr_text":"facebook/react  Public  The library for web and '
    'native user interfaces  230k stars  48k forks  JavaScript MIT license",'
    '"candidate_entities":[{"type":"repo","value":"facebook/react"}]}\n'
    "Example 2 - the IMDb page for Dune: Part Two:\n"
    '{"detected_service":"imdb","visible_url":"imdb.com/title/tt15239678",'
    '"title_guess":"Dune: Part Two","ocr_text":"Dune: Part Two  2024  PG-13  2h 46m  8.5/10  '
    'Sci-Fi Adventure  Directed by Denis Villeneuve",'
    '"candidate_entities":[{"type":"movie","value":"Dune: Part Two"},'
    '{"type":"year","value":"2024"},{"type":"imdb_id","value":"tt15239678"}]}\n'
    "Example 3 - a photo of a mountain trail with no text:\n"
    '{"detected_service":"generic","visible_url":null,"title_guess":null,"ocr_text":"",'
    '"candidate_entities":[]}'
)

VISION_USER = "Extract the signals from this image. Return only the JSON object."

GITHUB_DISAMBIGUATE_SYSTEM = (
    "Given OCR text from a screenshot, identify the single GitHub repository it refers to. "
    'Return ONLY {"owner":<string|null>,"repo":<string|null>,"confidence":<0..1>}. '
    "If you cannot identify a specific repo with reasonable certainty, return nulls and confidence 0.\n\n"
    'Example: ocr_text: "tailwindlabs/tailwindcss  A utility-first CSS framework  82k stars" -> '
    '{"owner":"tailwindlabs","repo":"tailwindcss","confidence":0.97}\n'
    'Example: ocr_text: "a really nice CSS framework I saw on Twitter, utility classes" -> '
    '{"owner":null,"repo":null,"confidence":0}'
)

MOVIE_PICK_SYSTEM = (
    "You are matching a shared item to the correct movie. You are given extracted context and a "
    'list of TMDb candidates. Return ONLY {"tmdb_id":<int|null>,"confidence":<0..1>}. '
    "Prefer an exact title + release-year match. If no candidate is a confident match, return "
    "null and a low confidence.\n\n"
    'Example input: {"context":{"title_guess":"Dune: Part Two","year":"2024"},'
    '"candidates":[{"id":693134,"title":"Dune: Part Two","release_year":2024},'
    '{"id":438631,"title":"Dune","release_year":2021}]} -> '
    '{"tmdb_id":693134,"confidence":0.98}\n'
    'Example input: {"context":{"title_guess":"Dune","year":null},'
    '"candidates":[{"id":438631,"title":"Dune","release_year":2021},'
    '{"id":841,"title":"Dune","release_year":1984}]} -> '
    '{"tmdb_id":null,"confidence":0.4}'
)

CATEGORIZE_SYSTEM = (
    "You file an enriched item into a category tree. You are given the item and the current tree "
    '(as JSON). Return ONLY {"categories":[<existing names>],"tags":[<strings>]}. '
    "Choose EVERY category that genuinely fits - an item may belong to several. "
    "Use only category names present in the provided tree. Propose tags freely (lowercase, "
    "singular). Do not invent categories.\n\n"
    'Example input: {"item":{"type":"github","title":"facebook/react","description":"The library '
    'for web and native user interfaces","attributes":{"stars":230000,"language":"JavaScript"}},'
    '"tree":["Development","Links","Movies","Articles","Products","Recipes","Papers","Social","Inbox"]} -> '
    '{"categories":["Development","Links"],"tags":["react","javascript","ui","frontend","library"]}\n'
    'Example input: {"item":{"type":"movie","title":"Dune: Part Two","description":"Paul Atreides '
    'unites with the Fremen...","attributes":{"rating":8.5,"genres":["Sci-Fi","Adventure"]}},'
    '"tree":["Development","Links","Movies","Articles","Products","Recipes","Papers","Social","Inbox"]} -> '
    '{"categories":["Movies"],"tags":["sci-fi","adventure","denis-villeneuve","2024"]}'
)

TEXT_SIGNALS_SYSTEM = (
    "You extract lightweight signals from a shared text snippet. Return ONLY minified JSON: "
    '{"detected_service":<enum>,"visible_url":<string|null>,"title_guess":<string|null>,'
    '"ocr_text":<string>,"candidate_entities":[{"type":<string>,"value":<string>}]} '
    'detected_service must be one of ["github","imdb","movie","youtube","twitter","product",'
    '"recipe","article","generic"]. Put the original text in ocr_text. '
    'Entity types: repo, movie, year, imdb_id, url, product, person, other. '
    'If unsure, use "generic" and an empty candidate_entities. Never output prose.'
)
