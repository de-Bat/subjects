from app.resolvers.github import github_icon


def test_uses_api_avatar_when_present():
    data = {"owner": {"avatar_url": "https://avatars.githubusercontent.com/u/1?v=4"}}
    assert github_icon(data, "facebook") == "https://avatars.githubusercontent.com/u/1?v=4"


def test_falls_back_to_owner_png_when_missing():
    assert github_icon({}, "facebook") == "https://github.com/facebook.png"
    assert github_icon({"owner": {}}, "vercel") == "https://github.com/vercel.png"
