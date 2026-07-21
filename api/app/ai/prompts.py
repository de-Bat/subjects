"""Production prompts (spec Appendix B). All demand ONLY minified JSON."""

VISION_SYSTEM = (
    "You extract structured signals from a shared image (usually a screenshot of a web page "
    "or social post). "
    'Return ONLY minified JSON of the form: '
    '{"detected_service":<enum>,"visible_url":<string|null>,"title_guess":<string|null>,'
    '"ocr_text":<string>,"reasoning":<string>,'
    '"candidate_entities":[{"type":<string>,"value":<string>}]} '
    'detected_service must be one of ["github","imdb","movie","youtube","twitter","instagram",'
    '"tiktok","product","recipe","article","generic"]. '
    "Detect the container service (instagram, tiktok, imdb...) from logos/URL/layout AND the "
    "subject independently: a movie or TV show promo posted on Instagram is still ABOUT that "
    "movie/show. "
    "Entity types you may emit: repo, movie, media_title, person, character, provider, studio, "
    "year, imdb_id, url, product, other. Use 'media_title' for a film/series title, 'person' for "
    "an actor/creator, and 'provider' for a streaming service (e.g. 'Apple TV+', 'Netflix'). "
    "reasoning is one short sentence describing what you see. "
    'If you cannot tell the service, use "generic". Never output prose, markdown, or explanations '
    "outside the JSON.\n\n"
    "Example 1 - the github.com/facebook/react repository page:\n"
    '{"detected_service":"github","visible_url":"github.com/facebook/react",'
    '"title_guess":"facebook/react","ocr_text":"facebook/react  Public  The library for web and '
    'native user interfaces  230k stars","reasoning":"GitHub repo page for facebook/react",'
    '"candidate_entities":[{"type":"repo","value":"facebook/react"}]}\n'
    "Example 2 - the IMDb page for Dune: Part Two:\n"
    '{"detected_service":"imdb","visible_url":"imdb.com/title/tt15239678",'
    '"title_guess":"Dune: Part Two","ocr_text":"Dune: Part Two  2024  PG-13  8.5/10",'
    '"reasoning":"IMDb title page for the film Dune: Part Two",'
    '"candidate_entities":[{"type":"movie","value":"Dune: Part Two"},'
    '{"type":"year","value":"2024"},{"type":"imdb_id","value":"tt15239678"}]}\n'
    "Example 3 - an Instagram reel from Apple TV showing Annette Bening in a series:\n"
    '{"detected_service":"instagram","visible_url":null,"title_guess":"Priscilla",'
    '"ocr_text":"ANNETTE BENING PRISCILLA  Apple TV  Annette Bening is in her villain era",'
    '"reasoning":"Instagram reel promoting the Apple TV+ series Priscilla",'
    '"candidate_entities":[{"type":"media_title","value":"Priscilla"},'
    '{"type":"person","value":"Annette Bening"},{"type":"provider","value":"Apple TV+"}]}'
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
    "You are matching a shared item to the correct movie OR TV show. You are given extracted "
    "context and a list of TMDb candidates, each tagged with media_type ('movie' or 'tv'). "
    'Return ONLY {"tmdb_id":<int|null>,"media_type":<"movie"|"tv"|null>,"confidence":<0..1>}. '
    "Prefer an exact title + release-year match; a TV show and a movie can share a title, so use "
    "the media_type of the candidate you pick. If no candidate is a confident match, return "
    "null and a low confidence.\n\n"
    'Example input: {"context":{"title_guess":"Priscilla","year":"2026"},'
    '"candidates":[{"id":220000,"media_type":"tv","title":"Priscilla","release_year":2026},'
    '{"id":842675,"media_type":"movie","title":"Priscilla","release_year":2023}]} -> '
    '{"tmdb_id":220000,"media_type":"tv","confidence":0.96}\n'
    'Example input: {"context":{"title_guess":"Dune","year":null},'
    '"candidates":[{"id":438631,"media_type":"movie","title":"Dune","release_year":2021},'
    '{"id":841,"media_type":"movie","title":"Dune","release_year":1984}]} -> '
    '{"tmdb_id":null,"media_type":null,"confidence":0.4}'
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
    'detected_service must be one of ["github","imdb","movie","youtube","twitter","instagram",'
    '"tiktok","product","recipe","article","generic"]. Put the original text in ocr_text. '
    'Entity types: repo, movie, year, imdb_id, url, product, person, media_title, provider, studio, character, other. '
    'If unsure, use "generic" and an empty candidate_entities. Never output prose.'
)
