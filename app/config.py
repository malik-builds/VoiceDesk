from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str

    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    valsea_api_key: str = ""

    stt_provider: str = "elevenlabs"
    tts_provider: str = "elevenlabs"

    supabase_url: str = ""
    supabase_anon_key: str = ""

    company_name: str = "Bright Smile Dental"
    receptionist_name: str = "George"
    custom_instructions: str = (
        "We are Bright Smile Dental, a modern dental practice in Melbourne. "
        "\n\nSERVICES & PRICING:"
        "\n- General check-up & clean: $120 (gap-free for most health fund members)"
        "\n- Tooth-coloured fillings: $180–$350 depending on size"
        "\n- Professional teeth whitening: $400 in-chair, $250 take-home kit"
        "\n- Root canal treatment: $800–$1,200 (molar costs more than front teeth)"
        "\n- Tooth extractions: $150 simple, up to $400 for surgical"
        "\n- Invisalign consultation: FREE — treatment pricing quoted after assessment"
        "\n- Emergency appointments: same-day available, call 03 9876 5432"
        "\n- Dental implants: from $3,500 per tooth (consult required)"
        "\n- Children's check-ups: bulk-billed under the Child Dental Benefits Schedule"
        "\n\nOUR TEAM:"
        "\n- Dr. Mei Chen — general dentistry, check-ups, fillings, preventative care"
        "\n- Dr. Arjun Patel — cosmetic dentistry, Invisalign, veneers, whitening"
        "\n- Dr. James Williams — oral surgery, extractions, implants, complex cases"
        "\n\nHOURS & LOCATION:"
        "\n- Monday–Friday: 8:00 am – 6:00 pm"
        "\n- Saturday: 9:00 am – 2:00 pm"
        "\n- Sunday: closed"
        "\n- Address: 42 Collins Street, Melbourne CBD, VIC 3000"
        "\n- Free parking available in the building on levels B1 and B2"
        "\n- Tram stop: Collins Street/Swanston Street (trams 1, 3, 5, 6, 16, 64, 67, 72)"
        "\n\nHEALTH FUNDS:"
        "\nWe are preferred providers for Medibank, BUPA, HCF, NIB, and HBF. "
        "We use HICAPS so you only pay your gap on the day. "
        "We accept all registered Australian health funds."
        "\n\nPOLICIES:"
        "\n- 24-hour cancellation notice required to avoid a $50 late cancellation fee"
        "\n- We send SMS reminders 48 hours before your appointment"
        "\n- Payment: cash, EFTPOS, credit card accepted. Payment plans via Afterpay"
        "\n\nEMERGENCY:"
        "\nFor dental emergencies (severe toothache, broken tooth, knocked-out tooth, "
        "lost filling/crown) call 03 9876 5432 directly. Do NOT ask them to wait for a callback."
    )

    cal_com_api_key: str = ""
    cal_com_event_type_id: int = 0
    cal_com_timezone: str = "Australia/Melbourne"


settings = Settings()
