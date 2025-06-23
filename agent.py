# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Shows how to call all the sub-agents using the LLM's reasoning ability. Run this with "adk run" or "adk web"
import datetime
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.agents import LlmAgent
from google.adk.tools import google_search
from google.adk.tools import agent_tool

from typing import Optional # Make sure to import Optional

from opik.integrations.adk import OpikTracer
from opik import track

# --- Creating telemetry sink ---
opik_tracer = OpikTracer()

from .util import load_instruction_from_file

# --- Sub Agent 1: Scriptwriter ---
def interview(name: Optional[str] = None) -> str:
    """Provides a greeting and initial set of questions. If a name is provided, it will be used.

    Args:
        name (str, optional): The name of the person to greet. Defaults to a generic greeting if not provided.

    Returns:
        str: A friendly greeting message.
    """
    interview = load_instruction_from_file("diet_interview_instruction.txt")
    print(interview)
    if name:
        greeting = f"Hello, {name}!"
#        print(f"--- Tool: interview called with name: {name} ---")
    else:
        greeting = "Hello there!" # Default greeting if name is None or not explicitly passed
#        print(f"--- Tool: interview called without a specific name (name_arg_value: {name}) ---")
    
    return greeting + interview

def say_goodbye() -> str:
    """Provides a simple farewell message to conclude the conversation."""
#    print(f"--- Tool: say_goodbye called ---")
    return "Goodbye! Have a great day."

def get_current_month_day() -> dict:
    """Returns the current month and day to use for seasonal planning.
    Returns:
        dict: A  dictionary containing the month and day information.
              Includes a 'status' key ('success' or 'error').
              If 'success', includes a 'report' key with month and day details.
              If 'error', includes an 'error_message' key
    """
    now = datetime.datetime.now()
    report = (
        f'The current month and day are {now.strftime("%B %d")}'
    )
    return {"status": "success", "report": report}

def get_current_season() -> str:
    """Returns the current season (Spring, Summer, Autumn, Winter).
    
    Returns:
        str: The current season name.
    """
    now = datetime.datetime.now()
    month = now.month
    
    if 3 <= month <= 5:
        return "Spring"
    elif 6 <= month <= 8:
        return "Summer"
    elif 9 <= month <= 11:
        return "Autumn"
    else:  # month == 12 or month <= 2
        return "Winter"
# --- Interview Agent ---
interview_agent = None
try:
    interview_agent = Agent(
        # Using a potentially different/cheaper model for a simple task
        model="gemini-2.0-flash-001",
        # model=LiteLlm(model=MODEL_GPT_4O), # If you would like to experiment with other models
        name="interview_agent",
        instruction="You are the Interview Agent. Your ONLY task is to provide a friendly greeting to the user and capture as much information about user as possible. "
                    "Use the 'interview' tool to generate the greeting and user attributes to capture. "
                    "If the user provides their name, make sure to pass it to the tool. "
                    "Do not engage in any other tasks.",
        description="Handles greetings and initial triage using the 'interview' tool.", # Crucial for delegation
        tools=[interview],
        output_key="user_profile",
    )
    print(f"✅ Agent '{interview_agent.name}' created using model '{interview_agent.model}'.")
except Exception as e:
    print(f"❌ Could not create Interview agent. Check API Key ({interview_agent.model}). Error: {e}")

# --- Farewell Agent ---
farewell_agent = None
try:
    farewell_agent = Agent(
        # Can use the same or a different model
        model="gemini-2.0-flash-001",
        # model=LiteLlm(model=MODEL_GPT_4O), # If you would like to experiment with other models
        name="farewell_agent",
        instruction="You are the Farewell Agent. Your ONLY task is to provide a polite goodbye message. "
                    "Use the 'say_goodbye' tool when the user indicates they are leaving or ending the conversation "
                    "(e.g., using words like 'bye', 'goodbye', 'thanks bye', 'see you'). "
                    "Do not perform any other actions.",
        description="Handles simple farewells and goodbyes using the 'say_goodbye' tool.", # Crucial for delegation
        tools=[say_goodbye],
    )
    print(f"✅ Agent '{farewell_agent.name}' created using model '{farewell_agent.model}'.")
except Exception as e:
    print(f"❌ Could not create Farewell agent. Check API Key ({farewell_agent.model}). Error: {e}")

Agent_Search = Agent(
    model='gemini-2.0-flash-exp',
    name='SearchAgent',
    description="Agent to answer questions and augument knowledge using Google Search.",
    instruction="""
    I can answer your questions by searching the internet. Just ask me anything!
    I'm an expert in Google Search and can retrieve current information to augument knowledge.
    """,
    tools=[google_search],
    after_agent_callback=opik_tracer.after_agent_callback,
    before_model_callback=opik_tracer.before_model_callback,
    after_model_callback=opik_tracer.after_model_callback,
    before_tool_callback=opik_tracer.before_tool_callback,
    after_tool_callback=opik_tracer.after_tool_callback,
)

diet_writer_agent = LlmAgent(
    name="Dietwriter",
    model="gemini-2.0-flash-001",
    instruction=load_instruction_from_file("dietwriter_instruction.txt"),
#    tools=[google_search], # see https://github.com/google/adk-python/issues/53#issuecomment-2798906767
    tools=[agent_tool.AgentTool(agent=Agent_Search), get_current_season, get_current_month_day],
    after_agent_callback=opik_tracer.after_agent_callback,
    before_model_callback=opik_tracer.before_model_callback,
    after_model_callback=opik_tracer.after_model_callback,
    before_tool_callback=opik_tracer.before_tool_callback,
    after_tool_callback=opik_tracer.after_tool_callback,
    output_key="generated_diet",  # Save result to state
)

grocery_promo_scout = LlmAgent(
    name="GroceryPromoScout",
    model="gemini-2.0-flash-001",
    instruction=load_instruction_from_file("grocery_specials.txt"),
    description="This agent searches local online stores with the ability to use **Google Search** to gather and organize grocery store specials in a structured, comparable format.",
    tools=[agent_tool.AgentTool(agent=Agent_Search), get_current_season, get_current_month_day],
    after_agent_callback=opik_tracer.after_agent_callback,
    before_model_callback=opik_tracer.before_model_callback,
    after_model_callback=opik_tracer.after_model_callback,
    before_tool_callback=opik_tracer.before_tool_callback,
    after_tool_callback=opik_tracer.after_tool_callback,
    output_key="generated_promos",  # Save result to state
)

grocery_shopper = LlmAgent(
    name="GroceryShopper",
    model="gemini-2.0-flash-001",
    instruction=load_instruction_from_file("grocery_shopper.txt"),
    description="This agent searches local online stores for each item on an input grocery list, compares prices across multiple retailers, selects the best available price for each item, and outputs a detailed itemized list with prices and the total estimated cost for the full grocery order.",
    tools=[agent_tool.AgentTool(agent=Agent_Search), get_current_season, get_current_month_day],
    after_agent_callback=opik_tracer.after_agent_callback,
    before_model_callback=opik_tracer.before_model_callback,
    after_model_callback=opik_tracer.after_model_callback,
    before_tool_callback=opik_tracer.before_tool_callback,
    after_tool_callback=opik_tracer.after_tool_callback,
    output_key="generated_diet",  # Save result to state
)

# --- Sub Agent 3: Formatter ---
# This agent would read both state keys and combine into the final Markdown
formatter_agent = LlmAgent(
    name="MarkdownFormatter",
    model="gemini-2.0-flash-001",
    instruction="""Combine the script from state['generated_diet'] into the final Markdown format (Hook, Table, Notes, CTA).""",
    description="Formats the final diet plan into Markdown format.",
    after_agent_callback=opik_tracer.after_agent_callback,
    before_model_callback=opik_tracer.before_model_callback,
    after_model_callback=opik_tracer.after_model_callback,
    before_tool_callback=opik_tracer.before_tool_callback,
    after_tool_callback=opik_tracer.after_tool_callback,
    output_key="final_diet_plan",
)

# --- Llm Agent Workflow ---
personalized_diet_agent = LlmAgent(
    name="personalized_diet_agent",
    model="gemini-2.0-flash-001",
    instruction=load_instruction_from_file("personalized_diet_agent_instruction.txt"),
#    description="You are an agent that can write diet plans, visuals and format diet plans. You have subagents that can do this",
    description="You are an agent that can identify **person** objectives and constraints and write diet plans. You have subagents that can do this",
#    tools=[agent_tool.AgentTool(agent=diet_writer_agent), agent_tool.AgentTool(agent=visualizer_agent), agent_tool.AgentTool(agent=formatter_agent)],
    tools=[
        agent_tool.AgentTool(agent=interview_agent), 
        agent_tool.AgentTool(agent=grocery_promo_scout),
        agent_tool.AgentTool(agent=diet_writer_agent),
        agent_tool.AgentTool(agent=grocery_shopper),
        agent_tool.AgentTool(agent=formatter_agent),
        agent_tool.AgentTool(agent=farewell_agent)
        ],
# , agent_tool.AgentTool(agent=visualizer_agent)    
    before_agent_callback=opik_tracer.before_agent_callback,
    after_agent_callback=opik_tracer.after_agent_callback,
    before_model_callback=opik_tracer.before_model_callback,
    after_model_callback=opik_tracer.after_model_callback,
    before_tool_callback=opik_tracer.before_tool_callback,
    after_tool_callback=opik_tracer.after_tool_callback,
)

# --- Root Agent for the Runner ---
# The runner will now execute the workflow
root_agent = personalized_diet_agent
