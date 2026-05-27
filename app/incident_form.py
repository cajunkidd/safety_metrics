"""Definition of the incident submission form.

Each field's `name` matches the exact column header used in the safety
manager's spreadsheet, so values flow straight into the same raw_data
shape as uploaded rows.
"""

YES_NO = ["", "Yes", "No"]
YES_NO_NA = ["", "Yes", "No", "N/A"]

INCIDENT_FORM_SECTIONS = [
    {
        "title": "Incident Details",
        "id": "incident",
        "show_when": None,
        "fields": [
            {"name": "When did this incident take place?", "label": "Date of incident", "type": "date", "required": True},
            {"name": "At approximately what time?", "label": "Time of incident", "type": "time"},
            {"name": "Store Location", "label": "Store location", "type": "text", "required": True, "placeholder": "e.g. 11 - Sulphur"},
            {"name": "Roughly, where did this happen?", "label": "Roughly, where did this happen?", "type": "text"},
            {"name": "Specific Location:", "label": "Specific location", "type": "text"},
            {"name": "What type of incident is this?", "label": "Type of incident", "type": "select", "options": ["", "Customer Incident", "Employee Incident"], "required": True, "trigger": "incident_type"},
            {"name": "Recordable", "label": "OSHA Recordable?", "type": "select", "options": ["", "Yes", "No"], "required": True},
            {"name": "Reason for Recordable Classification", "label": "Reason for recordable classification", "type": "textarea"},
            {"name": "Summarize the Incident:", "label": "Summary of the incident", "type": "textarea", "required": True},
        ],
    },
    {
        "title": "Reporter Information",
        "id": "reporter",
        "show_when": None,
        "fields": [
            {"name": "Who is completing this form?", "label": "Your name", "type": "text", "required": True},
            {"name": "What is your position with the company?", "label": "Your position", "type": "text"},
            {"name": "What is a good phone number to contact you on?", "label": "Your phone", "type": "tel"},
        ],
    },
    {
        "title": "Customer Information",
        "id": "customer",
        "show_when": ("incident_type", "Customer Incident"),
        "fields": [
            {"name": "Customer Name", "label": "Customer name", "type": "text"},
            {"name": "Customer Address", "label": "Customer address", "type": "text"},
            {"name": "Customer Phone Number, with area code.", "label": "Customer phone", "type": "tel"},
            {"name": "Customer Date of Birth", "label": "Customer date of birth", "type": "date"},
            {"name": "Sex", "label": "Sex", "type": "select", "options": ["", "Male", "Female", "Other"]},
            {"name": "Did customer give written statement?", "label": "Customer written statement?", "type": "select", "options": YES_NO},
            {"name": "What type of incident are you reporting?", "label": "What type of incident are you reporting?", "type": "text"},
        ],
    },
    {
        "title": "Employee Information",
        "id": "employee",
        "show_when": ("incident_type", "Employee Incident"),
        "fields": [
            {"name": "Employee Name", "label": "Employee name", "type": "text"},
            {"name": "Employee Number", "label": "Employee number", "type": "text"},
            {"name": "Employee Phone Number, with area code.", "label": "Employee phone", "type": "tel"},
            {"name": "Did employee involved give written statement?", "label": "Employee written statement?", "type": "select", "options": YES_NO},
            {"name": "What are you reporting", "label": "What are you reporting?", "type": "select", "options": ["", "Damage", "Injury", "Auto Accident", "Other"], "trigger": "employee_reporting"},
        ],
    },
    {
        "title": "Damage Details",
        "id": "damage",
        "show_when": ("employee_reporting", "Damage"),
        "fields": [
            {"name": "What was damaged?", "label": "What was damaged?", "type": "text"},
            {"name": "Specifics of what was damaged:", "label": "Specifics of what was damaged", "type": "textarea"},
            {"name": "How did the Damage occur?", "label": "How did the damage occur?", "type": "textarea"},
            {"name": "What is the extent of damages?", "label": "Extent of damages", "type": "text"},
            {"name": "Have you asked the customer to obtain 2 or more estimates?", "label": "Asked customer to obtain 2+ estimates?", "type": "select", "options": YES_NO},
            {"name": "Name of primary employee involved.", "label": "Primary employee involved", "type": "text"},
            {"name": "Name of secondary employee involved.", "label": "Secondary employee involved", "type": "text"},
            {"name": "Were there injuries involved with this damage?", "label": "Injuries with this damage?", "type": "select", "options": YES_NO},
        ],
    },
    {
        "title": "Injury Details",
        "id": "injury",
        "show_when": ("employee_reporting", "Injury"),
        "fields": [
            {"name": "What part of the body was most severely injured?", "label": "Body part most severely injured", "type": "text"},
            {"name": "Side of Body?", "label": "Side of body", "type": "select", "options": ["", "Left", "Right", "Both", "N/A"]},
            {"name": "What was the primary cause of the injury?", "label": "Primary cause of injury", "type": "text"},
            {"name": "How did the incident occur?", "label": "How did the incident occur?", "type": "textarea"},
            {"name": "Any unsafe actions or conditions that were a factor in the injury?", "label": "Unsafe actions or conditions", "type": "textarea"},
            {"name": "FOR EMPLOYEES ONLY:  What was PC365's recommended treatment?", "label": "PC365 recommended treatment", "type": "text"},
            {"name": "Please give summary of any first-aid given.", "label": "Summary of first-aid given", "type": "textarea"},
            {"name": "If PC365 was called - what is the reference number?", "label": "PC365 reference number", "type": "text"},
            {"name": "What medical facility was the employee sent to?  If Telemed, what is the date/time of the appointment?", "label": "Medical facility / Telemed appointment", "type": "text"},
        ],
    },
    {
        "title": "Auto Accident Details",
        "id": "auto",
        "show_when": ("employee_reporting", "Auto Accident"),
        "fields": [
            {"name": "Which police department came out to the scene?", "label": "Police department", "type": "text"},
            {"name": "What is the Police Report number?", "label": "Police report number", "type": "text"},
            {"name": "What company vehicle was the employee driving?", "label": "Company vehicle", "type": "text"},
            {"name": "What is the Year, Make, Model and Color of vehicle or trailer of the other party?", "label": "Other party's vehicle (Year/Make/Model/Color)", "type": "text"},
            {"name": "How did the Auto Accident occur?", "label": "How did the auto accident occur?", "type": "textarea"},
            {"name": "Where did the Auto Accident occur?", "label": "Where did the auto accident occur?", "type": "text"},
            {"name": "What is the name of the other driver?", "label": "Other driver's name", "type": "text"},
            {"name": "What is the STATE and LICENSE Number of the other driver?", "label": "Other driver's state & license #", "type": "text"},
            {"name": "What is the License Plate of the other party?", "label": "Other party's license plate", "type": "text"},
            {"name": "What is the address of the other driver?", "label": "Other driver's address", "type": "text"},
            {"name": "What is the phone number for the other driver?", "label": "Other driver's phone", "type": "tel"},
            {"name": "Was a citation issued for either party?  If yes, give details.", "label": "Citation issued? (details)", "type": "textarea"},
            {"name": "Were any injuries reported at the time of incident?", "label": "Injuries reported at scene?", "type": "select", "options": YES_NO},
            {"name": "What injuries is our employee(s) reporting?", "label": "Our employee's reported injuries", "type": "textarea"},
            {"name": "What injuries is the other party reporting?", "label": "Other party's reported injuries", "type": "textarea"},
            {"name": "If anyone was taken to the hospital, give details.", "label": "Hospital details", "type": "textarea"},
        ],
    },
    {
        "title": "Other Incident Details",
        "id": "other",
        "show_when": ("employee_reporting", "Other"),
        "fields": [
            {"name": "What incident occurred?  Please give extensive details.", "label": "What incident occurred? (detailed)", "type": "textarea"},
            {"name": "Names of people involved, and please be detailed with their involvement", "label": "People involved", "type": "textarea"},
        ],
    },
    {
        "title": "Documentation",
        "id": "documentation",
        "show_when": None,
        "fields": [
            {"name": "Please list any other witnesses and their involvement:", "label": "Witnesses and their involvement", "type": "textarea"},
            {"name": "How many witness statements have been received, total?", "label": "Witness statements received (count)", "type": "number"},
            {"name": "How many photos were taken and by whom?", "label": "Photos taken and by whom", "type": "text"},
            {"name": "Is there video footage of the incident available?", "label": "Video footage available?", "type": "select", "options": YES_NO},
            {"name": "Was a drug screen complete by associate involved?", "label": "Drug screen completed?", "type": "select", "options": YES_NO_NA},
        ],
    },
    {
        "title": "Comments & Attachments",
        "id": "comments",
        "show_when": None,
        "fields": [
            {"name": "Please give any additional comments, questions, concerns you have related to this incident.", "label": "Additional comments, questions, concerns", "type": "textarea"},
            {"name": "Where were witness reports submitted?", "label": "Where were witness reports submitted?", "type": "text"},
            {"name": "Who were photos submitted to?", "label": "Who were photos submitted to?", "type": "text"},
            {"name": "Who is the main person to contact regarding this incident?", "label": "Main contact for this incident", "type": "text"},
            {"name": "Please attach any witness statements, photos, estimates.", "label": "Attachments (describe what is attached)", "type": "textarea"},
        ],
    },
]


def all_field_names():
    return [
        field["name"]
        for section in INCIDENT_FORM_SECTIONS
        for field in section["fields"]
    ]


def required_field_names():
    return [
        field["name"]
        for section in INCIDENT_FORM_SECTIONS
        for field in section["fields"]
        if field.get("required")
    ]
