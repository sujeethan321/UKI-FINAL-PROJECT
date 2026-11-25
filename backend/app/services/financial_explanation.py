# Purpose: Construct and validate explanations against authorized financial facts before rendering them as user-facing text.
"""The model can select/order reviewed sections, never write financial prose.

Numbers and wording are rendered locally. Exact section/metric/observation
bindings are checked even after provider JSON-schema validation. No SQL/tools.
"""
import json
from app.integrations.ai.base import GenerationRequest,GenerationResult

MODEL='openai/gpt-oss-120b'

# Build a constrained explanation request from the allowed section and fact identifiers.
def request(context,sections,language):
    section_ids=[s['section_id'] for s in sections]
    fact_ids=sorted({fact for s in sections for fact in s['fact_ids']})
    schema={'type':'object','additionalProperties':False,'required':['language','sections'],'properties':{
        'language':{'type':'string','enum':[language]},
        'sections':{'type':'array','minItems':len(sections),'maxItems':len(sections),'items':{
            'type':'object','additionalProperties':False,'required':['section_id','fact_ids','observation'],
            'properties':{'section_id':{'type':'string','enum':section_ids},
                'fact_ids':{'type':'array','items':{'type':'string','enum':fact_ids}},
                'observation':{'type':'string','enum':sorted({s['observation'] for s in sections})}}}}}}
    return GenerationRequest(
        system_prompt='Return only the required JSON in the requested language code. Order every approved section once. Copy each section\'s fact_ids and observation exactly. No amounts, prose, tools, SQL, identities or additional fields. Backend templates supply all financial explanations.',
        user_prompt=json.dumps({'facts':context,'approved_sections':sections,'language':language},ensure_ascii=False,separators=(',',':')),
        response_schema=schema)

# Validate the completed explanation against the allowed model, output shape, and authorized fact identifiers.
def validate(result,sections,language):
    if not isinstance(result,GenerationResult) or result.model!=MODEL or result.finish_reason!='stop' or len(result.text.encode())>16000:raise ValueError('Invalid completion')
    # Reject duplicate JSON keys so contradictory provider fields cannot be silently replaced.
    def unique(pairs):
        output={}
        for key,value in pairs:
            if key in output:raise ValueError('Duplicate field')
            output[key]=value
        return output
    value=json.loads(result.text,object_pairs_hook=unique)
    if not isinstance(value,dict) or set(value)!={'language','sections'} or value['language']!=language or not isinstance(value['sections'],list) or len(value['sections'])!=len(sections):raise ValueError('Invalid structured response')
    expected={s['section_id']:s for s in sections};seen=set()
    for section in value['sections']:
        if not isinstance(section,dict) or set(section)!={'section_id','fact_ids','observation'} or not isinstance(section['section_id'],str):raise ValueError('Invalid section')
        ident=section['section_id']
        if ident in seen or ident not in expected or section!=expected[ident]:raise ValueError('Unverified metric attribution')
        seen.add(ident)
    return value['sections']

LABELS={
 'period_credit_sales':('Period net credit sales','காலப்பகுதியின் நிகரக் கடன் விற்பனை','කාල සීමාවේ ශුද්ධ ණය විකුණුම්'),
 'period_repayments':('Period net repayments','காலப்பகுதியின் நிகரத் திருப்பிச் செலுத்தல்கள்','කාල සීමාවේ ශුද්ධ ආපසු ගෙවීම්'),
 'current_outstanding':('Current outstanding','தற்போதைய நிலுவை','වත්මන් හිඟ මුදල'),
 'current_advances':('Current customer advances','தற்போதைய வாடிக்கையாளர் முன்பணம்','වත්මන් පාරිභෝගික අත්තිකාරම්'),
 'collected_today':('Collected today, net of reversals','இன்று வசூலித்தது, மீளாக்கங்களுக்குப் பின்','ප්‍රතිවර්තන අඩු කළ අද එකතුව'),
 'overdue':('Overdue amount','காலம் கடந்த தொகை','කල් ඉකුත් මුදල'),
 'aging_current':('Current','நடப்பு','වත්මන්'),
 'aging_days_1_30':('1–30 days overdue','1–30 நாட்கள் கடந்தது','දින 1–30 කල් ඉකුත්'),
 'aging_days_31_60':('31–60 days overdue','31–60 நாட்கள் கடந்தது','දින 31–60 කල් ඉකුත්'),
 'aging_days_61_90':('61–90 days overdue','61–90 நாட்கள் கடந்தது','දින 61–90 කල් ඉකුත්'),
 'aging_days_91_plus':('91+ days overdue','91+ நாட்கள் கடந்தது','දින 91+ කල් ඉකුත්'),
 'unclassified':('Unclassified','வகைப்படுத்தப்படாதது','වර්ගීකරණය නොකළ'),
 'account_credit_purchases':('Effective credit purchases','செயலிலுள்ள கடன் கொள்முதல்','බලපැවැත්වෙන ණය මිලදී ගැනීම්'),
 'account_repayments':('Effective repayments','செயலிலுள்ள திருப்பிச் செலுத்தல்கள்','බලපැවැත්වෙන ආපසු ගෙවීම්'),
}
TEXT={
 'scope':('Customer-credit ledger only: Driver fees, cash order sales, profit and platform revenue are not included. This explanation does not confirm a new payment or collection.','வாடிக்கையாளர் கடன் பதிவுகள் மட்டும்: ஓட்டுநர் கட்டணங்கள், பண விற்பனைகள், இலாபம் மற்றும் தள வருவாய் சேர்க்கப்படவில்லை. இந்த விளக்கம் புதிய கொடுப்பனவையோ வசூலையோ உறுதிப்படுத்தாது.','පාරිභෝගික ණය ලෙජරය පමණි: රියදුරු ගාස්තු, මුදල් ඇණවුම් විකුණුම්, ලාභ සහ වේදිකා ආදායම් ඇතුළත් නොවේ. මෙම පැහැදිලි කිරීම නව ගෙවීමක් හෝ එකතු කිරීමක් තහවුරු නොකරයි.'),
 'unavailable':('Unavailable','கிடைக்கவில்லை','නොමැත'),
 'current':('Balances are current, not historical period-end balances. Debt and advances remain separate per account.','நிலுவைகள் தற்போதையவை; வரலாற்றுக் கால முடிவு நிலுவைகள் அல்ல. கடனும் முன்பணமும் கணக்குவாரியாகத் தனித்தனியே உள்ளன.','ශේෂ වත්මන් අගයන්ය; පෙර කාල සීමා අවසාන ශේෂ නොවේ. ණය සහ අත්තිකාරම් එක් එක් ගිණුමට වෙනම තබා ඇත.'),
 'period':('Period movements include reversals on their recorded dates. Negative movements are possible. These are customer-credit figures, not platform revenue or Driver fees.','காலப்பகுதி நகர்வுகளில் பதிவு செய்யப்பட்ட தேதிகளிலான மீளாக்கங்கள் உள்ளன; எதிர்மறைத் தொகைகள் இருக்கலாம். இவை வாடிக்கையாளர் கடன் விவரங்கள்; தள வருவாயோ ஓட்டுநர் கட்டணமோ அல்ல.','කාල සීමා චලනවල ප්‍රතිවර්තන ඒවා වාර්තා කළ දිනට ඇතුළත්ය. ඍණ අගයන් තිබිය හැක. මේවා පාරිභෝගික ණය අගයන්ය; වේදිකා ආදායම් හෝ රියදුරු ගාස්තු නොවේ.'),
 'fifo':('FIFO is a reporting assumption, not persisted repayment allocation.','FIFO என்பது அறிக்கையிடல் அனுமானம்; சேமிக்கப்பட்ட திருப்பிச் செலுத்தல் ஒதுக்கீடு அல்ல.','FIFO වාර්තාකරණ උපකල්පනයකි; සුරැකි ආපසු ගෙවීම් වෙන් කිරීමක් නොවේ.'),
 'complete':('Unpaid debt is fully classified; aging reconciles with current outstanding under FIFO.','செலுத்தப்படாத கடன் முழுவதும் வகைப்படுத்தப்பட்டுள்ளது; FIFO அடிப்படையில் வயதுப் பகுப்பும் தற்போதைய நிலுவையும் ஒத்துள்ளன.','නොගෙවූ ණය සම්පූර්ණයෙන් වර්ගීකරණය කර ඇත; FIFO අනුව කාල විශ්ලේෂණය වත්මන් හිඟයට සැසඳේ.'),
 'incomplete':('Coverage is incomplete. An exact total overdue amount is unavailable.','தகவல் முழுமையில்லை. துல்லியமான மொத்தக் காலம் கடந்த தொகை கிடைக்கவில்லை.','ආවරණය අසම්පූර්ණය. නිශ්චිත මුළු කල් ඉකුත් මුදල නොමැත.'),
 'aging_unavailable':('Aging coverage and reconciliation are unavailable; no exact overdue total is asserted.','வயதுப் பகுப்பு மற்றும் ஒப்பீடு கிடைக்கவில்லை; துல்லியமான காலம் கடந்த மொத்தம் கூறப்படவில்லை.','කාල විශ්ලේෂණ ආවරණය හා සැසඳීම නොමැත; නිශ්චිත කල් ඉකුත් එකතුවක් ප්‍රකාශ නොකරයි.'),
 'intervals':('First and last interval totals; interval lengths may differ. No growth rate or forecast is inferred.','முதல் மற்றும் இறுதி இடைவெளித் தொகைகள்; இடைவெளி நீளங்கள் மாறலாம். வளர்ச்சி விகிதமோ முன்னறிவிப்போ ஊகிக்கப்படவில்லை.','පළමු හා අවසාන කාල කොටස් එකතුව; කොටස් දිග වෙනස් විය හැක. වර්ධන අනුපාතයක් හෝ පුරෝකථනයක් නිගමනය නොකරයි.'),
 'account':('Overdue is unavailable in this account summary. No due dates, payments, collections or commitments are inferred.','இந்தக் கணக்குச் சுருக்கத்தில் காலம் கடந்த தொகை கிடைக்கவில்லை. தவணைத் தேதிகள், கொடுப்பனவுகள், வசூல்கள் அல்லது வாக்குறுதிகள் ஊகிக்கப்படவில்லை.','මෙම ගිණුම් සාරාංශයේ කල් ඉකුත් මුදල නොමැත. ගෙවීම් දින, ගෙවීම්, එකතු කිරීම් හෝ පොරොන්දු උපකල්පනය නොකරයි.'),
 'coverage_counts':('Effective sales: {sales}; missing due dates: {missing}; invalid due dates: {invalid}.','செயலிலுள்ள விற்பனைகள்: {sales}; இல்லாத தவணைத் தேதிகள்: {missing}; செல்லாத தவணைத் தேதிகள்: {invalid}.','බලපැවැත්වෙන විකුණුම්: {sales}; නොමැති ගෙවීම් දින: {missing}; වලංගු නොවන ගෙවීම් දින: {invalid}.'),
}

# Select the fixed explanatory phrase for English, Tamil, or Sinhala.
def phrase(key,language):return TEXT[key][{'en':0,'ta':1,'si':2}[language]]

# Render one validated financial fact through the supported language phrases.
def render_fact(ident,value,language):
    label=LABELS[ident][{'en':0,'ta':1,'si':2}[language]]
    return label+': '+(phrase('unavailable',language) if value is None else 'LKR '+value)+'.'
