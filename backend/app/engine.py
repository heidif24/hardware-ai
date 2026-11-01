import json, os
from openai import OpenAI
from .models import SynthesisRequest, DesignResponse

SYSTEM = """You are a principal electronics systems architect preparing a rigorous early-stage engineering definition for a hardware product. This is NOT a schematic or PCB autorouter. Translate the user brief into a structured product requirements baseline and engineering plan.

Return valid JSON with keys: product_name, summary, assumptions, modules, risks, validation_status, estimated_complexity, requirements, electrical_design, interface_control, firmware_plan, mechanical_plan, verification_plan.
modules is a list of objects with id, name (one of Power, Processing, Sensing, Connectivity, Interface, Actuation), purpose, interfaces, status, parts.
Use only relevant modules. Give useful product-specific detail, not generic filler. Define measurable requirements only when supported by the brief; otherwise mark them TBD and explain what must be decided. Identify power domains, signal interfaces, protection, antenna/RF issues, environmental and mechanical constraints, firmware responsibilities, test procedures and certification considerations where relevant.
Never invent exact manufacturer part numbers, datasheets, electrical ratings, footprints, verified stock, prices, Gerbers, PCB layout, CAD models or test results. Candidate parts must remain functional classes until engineered and verified. Do not imply ERC, DRC, simulation, prototype testing or certification has occurred. Always set validation_status to concept_only and include concrete risks and missing information."""

def baseline(request: SynthesisRequest):
    brief = request.idea.lower()
    modules = []
    def add(name, purpose, parts, interfaces):
        modules.append({"id": name.lower(), "name": name, "purpose": purpose, "parts": parts, "interfaces": interfaces, "status": "concept"})
    add("Power", "Define input source, energy storage, power conversion, protection and duty-cycle budget.", [
        "Input power connector and transient protection to be specified",
        "Battery chemistry and capacity to be sized from duty cycle",
        "Charger / power-path controller if rechargeable",
        "Regulated DC-DC and low-noise rails as required",
        "Over-current, reverse-polarity and thermal protection"
    ], ["input power", "battery bus", "regulated rails", "power-good"])
    add("Processing", "Define control, data handling, timing, firmware and debug architecture.", [
        "MCU selected against peripheral, memory, compute and low-power requirements",
        "Non-volatile memory if required",
        "Programming and debug connector",
        "Clock and reset circuitry"
    ], ["I2C / SPI / UART as selected", "GPIO", "SWD/JTAG"])
    if any(word in brief for word in ["gps", "location", "tracker", "cattle"]):
        add("Sensing", "Acquire positioning and optional motion data.", [
            "GNSS receiver selected for constellation and accuracy needs",
            "Matched GNSS antenna and RF feed",
            "3-axis accelerometer if motion detection is required"
        ], ["UART", "I2C", "RF antenna feed"])
    else:
        add("Sensing", "Acquire application-specific physical measurements.", [
            "Sensor selected after range, accuracy and environment are specified",
            "Signal conditioning, filtering and input protection"
        ], ["I2C / SPI / ADC as selected", "sensor power", "interrupt"])
    if any(word in brief for word in ["cellular", "gps", "tracker", "remote", "wireless", "connected"]):
        add("Connectivity", "Define the communications stack, regional radio bands, antenna and certification path.", [
            "Cellular / LPWAN / Wi-Fi module selected for target region and coverage",
            "SIM/eSIM interface if cellular",
            "RF matching network and antenna keep-out",
            "ESD and RF coexistence provisions"
        ], ["UART / USB as selected", "RF", "SIM/eSIM"])
    if any(word in brief for word in ["display", "screen", "button", "e-ink"]):
        add("Interface", "Provide local status, controls and user feedback.", [
            "Display selected for size, power, readability and temperature",
            "Buttons / LEDs / buzzer as required",
            "ESD-protected user-accessible connections"
        ], ["SPI / I2C", "GPIO", "backlight or display power"])
    if any(word in brief for word in ["motor", "valve", "pump", "irrigation", "actuator"]):
        add("Actuation", "Control external loads with appropriate electrical isolation and protection.", [
            "MOSFET / relay / motor driver sized to load voltage and current",
            "Flyback or transient suppression",
            "Current sensing and fault feedback if required"
        ], ["PWM / GPIO", "protected power output", "fault feedback"])
    return {
        "product_name": " ".join(request.idea.split()[:7]).strip(".,"),
        "summary": "First-pass product architecture. Electrical sizing, exact components, circuit capture, mechanical CAD and validation remain to be completed.",
        "assumptions": [
            "Operating environment, service life and ingress-protection target require confirmation.",
            "Power budget and runtime require a quantified duty-cycle model.",
            "Target-market regulatory and radio requirements must be established.",
            "All component descriptions are candidate functional classes, not approved parts."
        ],
        "modules": modules,
        "risks": [
            "No circuit-level schematic, ERC, signal-integrity analysis or thermal simulation has been performed.",
            "No PCB layout, Gerbers, drill data or pick-and-place file has been generated.",
            "Battery, charging, RF, isolation and enclosure safety depend on final product requirements.",
            "Prototype, EMC, environmental and reliability testing remain outstanding."
        ],
        "validation_status": "concept_only",\n        "generation_mode": "rule_based_fallback",
        "estimated_complexity": "MEDIUM",
        "requirements": [
            "Confirm intended users, operating environment and installation method.",
            "Define product dimensions, mass, ingress protection and service life.",
            "Define measurable functional performance and acceptable tolerances.",
            "Define input power, average/peak current and required runtime.",
            "Define target market, regulatory region and required certifications."
        ],
        "electrical_design": [
            "Create a power tree with input range, protection, conversion efficiency and rail tolerances.",
            "Define every signal, voltage domain, connector and external interface.",
            "Select exact components only after datasheet and lifecycle review.",
            "Complete schematic capture, ERC and relevant electrical simulations."
        ],
        "interface_control": [
            "Create a connector schedule with pin number, signal name, direction, voltage and protection.",
            "Document communication protocols, addresses, baud rates and timing.",
            "Specify external load characteristics and isolation requirements.",
            "Reserve RF keep-outs and antenna matching requirements where applicable."
        ],
        "firmware_plan": [
            "Define boot, watchdog, fault handling and safe-state behaviour.",
            "Define sensor acquisition, filtering, calibration and data logging.",
            "Define communications protocol, provisioning and secure update requirements.",
            "Define low-power states, telemetry and diagnostic logging."
        ],
        "mechanical_plan": [
            "Establish board envelope, connector access and mounting constraints.",
            "Select enclosure material and process against environment and cost target.",
            "Assess thermal paths, ingress protection, vibration and drop requirements.",
            "Produce dimensioned CAD and STEP only after the PCB envelope is stable."
        ],
        "verification_plan": [
            "Review requirements traceability and test acceptance criteria.",
            "Perform power, interface and protection bench tests on prototypes.",
            "Perform firmware functional, fault-injection and recovery tests.",
            "Perform thermal, vibration, ingress and EMC testing as applicable.",
            "Record results and obtain engineering sign-off before fabrication release."
        ]
    }

async def synthesize(request: SynthesisRequest) -> DesignResponse:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return DesignResponse.model_validate(baseline(request))
    try:
        client = OpenAI(api_key=key)
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": json.dumps(request.model_dump())}
            ],
            timeout=60
        )
        data = json.loads(response.choices[0].message.content or "{}")
        data["validation_status"] = "concept_only"\n        data["generation_mode"] = "openai_structured"
        return DesignResponse.model_validate(data)
    except Exception:
        return DesignResponse.model_validate(baseline(request))
