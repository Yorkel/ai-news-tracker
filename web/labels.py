"""
web/labels.py — display names for sources.

The dashboard used to title-case the config key, which produced "Four Zero
Four Media", "Nyt Tech" and "Google News Ni". Publication names are not
derivable from a slug, so they are listed.

Anything not listed falls back to the old title-cased key, so a newly added
source still shows something sensible.
"""

from __future__ import annotations

DISPLAY = {
    # Mainstream press
    "four_zero_four_media": "404 Media", "nyt_tech": "New York Times",
    "ft_tech": "Financial Times", "bbc_tech": "BBC", "guardian_ai": "The Guardian",
    "politico_tech": "Politico", "the_markup": "The Markup",
    "rest_of_world": "Rest of World", "mit_tech_review_ai": "MIT Technology Review",
    "conversation_uk_tech": "The Conversation", "nature_news": "Nature",
    "science_news": "Science", "techcrunch_ai": "TechCrunch",
    "verge_ai": "The Verge", "arstechnica_ai": "Ars Technica",
    "wired_ai": "WIRED", "theregister_ai": "The Register",
    "zdnet_ai": "ZDNet", "venturebeat_ai": "VentureBeat",
    "ai_business": "AI Business", "lighthouse_reports": "Lighthouse Reports",
    # Google News jurisdiction queries
    "google_news_uk": "Google News · UK", "google_news_scotland": "Google News · Scotland",
    "google_news_wales": "Google News · Wales", "google_news_ni": "Google News · N. Ireland",
    "google_news_ireland": "Google News · Ireland", "google_news_eu": "Google News · EU",
    # Ireland
    "rte_brainstorm": "RTÉ Brainstorm", "rte_news_tech": "RTÉ News",
    "silicon_republic": "Silicon Republic", "irish_tech_news": "Irish Tech News",
    "thejournal_ie": "TheJournal.ie", "irish_independent": "Irish Independent",
    "irish_examiner": "Irish Examiner", "dublin_inquirer": "Dublin Inquirer",
    "the_currency": "The Currency", "business_post": "Business Post",
    "iccl": "ICCL", "coimisiun_na_mean": "Coimisiún na Meán",
    "ronan_kennedy": "Rónán Kennedy",
    # UK / EU institutions
    "govuk_ai_search": "GOV.UK", "dsit": "DSIT", "cabinet_office": "Cabinet Office",
    "gds_blog": "GDS", "commons_library": "Commons Library", "nao": "NAO",
    "ai_security_institute": "AI Security Institute",
    "institute_for_government": "Institute for Government",
    "ec_digital_strategy": "European Commission", "edpb": "EDPB",
    "europarl_press": "European Parliament", "fra_eu": "EU Fundamental Rights Agency",
    "eu_ai_act_tracker": "EU AI Act tracker", "public_technology": "PublicTechnology",
    "statescoop": "StateScoop",
    # Civil society
    "big_brother_watch": "Big Brother Watch", "open_rights_group": "Open Rights Group",
    "public_law_project": "Public Law Project", "connected_by_data": "Connected by Data",
    "we_and_ai": "We and AI", "edri": "EDRi", "access_now": "Access Now",
    "algorithmwatch": "AlgorithmWatch", "ai_now_institute": "AI Now Institute",
    "the_ferret": "The Ferret", "ai4people": "AI4People",
    # Safety and research
    "metr": "METR", "govai": "GovAI", "cset": "CSET", "miri": "MIRI",
    "redwood_research": "Redwood Research", "alignment_forum": "Alignment Forum",
    "lesswrong": "LessWrong", "cais_safety_newsletter": "CAIS Safety Newsletter",
    "ai_futures_project": "AI Futures Project", "forethought": "Forethought",
    "ai_frontiers": "AI Frontiers", "frontier_model_forum": "Frontier Model Forum",
    "deepmind_safety_research": "DeepMind Safety Research",
    "forecasting_research_institute": "Forecasting Research Institute",
    "inspect_ai_releases": "AISI Inspect", "bluedot_impact": "BlueDot Impact",
    "council_strategic_risks": "Council on Strategic Risks",
    "arxiv_cs_cy": "arXiv cs.CY", "arxiv_cs_ai": "arXiv cs.AI", "arxiv_cs_lg": "arXiv cs.LG",
    "nist": "NIST", "bruegel": "Bruegel",
    # Newsletters and individuals
    "normal_tech": "Normal Tech", "tech_policy_press": "Tech Policy Press",
    "import_ai": "Import AI", "interconnects": "Interconnects",
    "dont_worry_about_the_vase": "Don't Worry About the Vase",
    "blood_in_the_machine": "Blood in the Machine", "platformer": "Platformer",
    "transformer": "Transformer", "simon_willison": "Simon Willison",
    "peter_wildeford": "Peter Wildeford", "miles_brundage": "Miles Brundage",
    "jan_leike": "Jan Leike", "victoria_krakovna": "Victoria Krakovna",
    "neel_nanda": "Neel Nanda", "lilian_weng": "Lilian Weng",
    "sebastian_raschka": "Sebastian Raschka", "planned_obsolescence": "Planned Obsolescence",
    "conspicuous_cognition": "Conspicuous Cognition", "mozilla": "Mozilla",
    # Labs and tooling
    "openai": "OpenAI", "deepmind": "Google DeepMind", "huggingface": "Hugging Face",
    # Podcasts
    "eighty_thousand_hours": "80,000 Hours", "axrp": "AXRP",
    "redwood_podcast": "Redwood Research (audio)", "dwarkesh": "Dwarkesh Podcast",
    "cognitive_revolution": "Cognitive Revolution", "mlst": "Machine Learning Street Talk",
    "robert_miles": "Robert Miles", "chinatalk": "ChinaTalk", "lawfare": "Lawfare",
    "hard_fork": "Hard Fork", "latent_space": "Latent Space",
    "practical_ai": "Practical AI", "gradient_dissent": "Gradient Dissent",
    "mystery_ai_hype": "Mystery AI Hype Theater 3000",
    "tech_wont_save_us": "Tech Won't Save Us", "last_week_in_ai": "Last Week in AI",
}


def display(source: str) -> str:
    if source in DISPLAY:
        return DISPLAY[source]
    from dashboard.config import source_label
    return source_label(source)
