"""
Enhanced Natural Language Understanding for Moses AI Assistant
Provides advanced parsing, intent recognition, and context-aware processing
"""

import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from azure_openai import ask_openai

class IntentClassifier:
    """Classifies user intents and extracts structured data"""
    
    INTENT_PATTERNS = {
        'task_management': [
            r'\b(add|create|new|make)\s+(task|todo|reminder)',
            r'\b(complete|finish|done|mark)\s+(task|todo)',
            r'\b(delete|remove|cancel)\s+(task|todo)',
            r'\b(show|list|view)\s+(tasks|todos)',
            r'\b(update|edit|change)\s+(task|todo)',
            r'\bdeadline\b',
            r'\bpriority\b',
            r'\bdue\s+(by|on|before)',
        ],
        'budget_management': [
            r'\b(spent|spend|cost|paid|pay)\s*\$?\d+',
            r'\b(earned|income|salary|received)\s*\$?\d+',
            r'\b(budget|expense|expenses|spending)',
            r'\b(track|record|log)\s+(expense|spending|income)',
            r'\b(show|view|check)\s+(budget|expenses|spending)',
            r'\$\d+',
        ],
        'schedule_management': [
            r'\b(schedule|appointment|meeting|event)',
            r'\b(calendar|agenda)',
            r'\b(remind|reminder)\s+me',
            r'\b(at|on|from|until)\s+\d{1,2}(:\d{2})?\s*(am|pm)',
            r'\b(today|tomorrow|next\s+week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'\b(book|reserve|plan)',
        ],
        'information_query': [
            r'\b(what|when|where|how|why|who)',
            r'\b(show|tell|explain|describe)',
            r'\b(status|summary|overview|report)',
            r'\b(help|assist|support)',
        ],
        'conversation': [
            r'\b(hello|hi|hey|good\s+(morning|afternoon|evening))',
            r'\b(thank|thanks|appreciate)',
            r'\b(how\s+are\s+you|what\'s\s+up)',
            r'\b(bye|goodbye|see\s+you)',
        ]
    }
    
    def classify_intent(self, text: str) -> List[str]:
        """Classify the primary intent(s) of the user input"""
        text_lower = text.lower()
        detected_intents = []
        
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    if intent not in detected_intents:
                        detected_intents.append(intent)
                    break
        
        # If no specific intent detected, default to conversation
        if not detected_intents:
            detected_intents.append('conversation')
            
        return detected_intents

class AdvancedEntityExtractor:
    """Extracts entities like dates, times, amounts, priorities from text"""
    
    def __init__(self):
        self.date_patterns = [
            r'\b(today|tomorrow)\b',
            r'\b(next|this)\s+(week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
            r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}\b',
            r'\bin\s+\d+\s+(days?|weeks?|months?)\b',
        ]
        
        self.time_patterns = [
            r'\b\d{1,2}(:\d{2})?\s*(am|pm)\b',
            r'\b(morning|afternoon|evening|night)\b',
            r'\bat\s+\d{1,2}(:\d{2})?\b',
        ]
        
        self.amount_patterns = [
            r'\$\d+(\.\d{2})?',
            r'\b\d+\s*dollars?\b',
            r'\b\d+(\.\d{2})?\s*bucks?\b',
        ]
        
        self.priority_patterns = [
            r'\b(urgent|asap|immediately|critical|high\s+priority)\b',
            r'\b(important|medium\s+priority)\b',
            r'\b(low\s+priority|when\s+possible|eventually)\b',
        ]
    
    def extract_dates(self, text: str) -> List[str]:
        """Extract date references from text"""
        dates = []
        text_lower = text.lower()
        
        for pattern in self.date_patterns:
            matches = re.findall(pattern, text_lower)
            dates.extend(matches)
        
        return self._normalize_dates(dates)
    
    def extract_times(self, text: str) -> List[str]:
        """Extract time references from text"""
        times = []
        text_lower = text.lower()
        
        for pattern in self.time_patterns:
            matches = re.findall(pattern, text_lower)
            times.extend([match[0] if isinstance(match, tuple) else match for match in matches])
        
        return times
    
    def extract_amounts(self, text: str) -> List[float]:
        """Extract monetary amounts from text"""
        amounts = []
        
        for pattern in self.amount_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                # Extract numeric value
                numeric = re.findall(r'\d+(\.\d{2})?', match)
                if numeric:
                    amounts.append(float(numeric[0][0] if isinstance(numeric[0], tuple) else numeric[0]))
        
        return amounts
    
    def extract_priority(self, text: str) -> int:
        """Extract priority level from text (1=low, 2=medium, 3=high, 4=urgent)"""
        text_lower = text.lower()
        
        if re.search(self.priority_patterns[0], text_lower):  # urgent
            return 4
        elif re.search(self.priority_patterns[1], text_lower):  # important
            return 3
        elif re.search(self.priority_patterns[2], text_lower):  # low
            return 1
        else:
            return 2  # default medium
    
    def _normalize_dates(self, date_strings: List[str]) -> List[str]:
        """Convert relative dates to absolute dates"""
        normalized = []
        today = datetime.now()
        
        for date_str in date_strings:
            if date_str == 'today':
                normalized.append(today.strftime('%Y-%m-%d'))
            elif date_str == 'tomorrow':
                normalized.append((today + timedelta(days=1)).strftime('%Y-%m-%d'))
            elif 'next week' in date_str:
                normalized.append((today + timedelta(weeks=1)).strftime('%Y-%m-%d'))
            elif 'next month' in date_str:
                normalized.append((today + timedelta(days=30)).strftime('%Y-%m-%d'))
            else:
                normalized.append(date_str)
        
        return normalized

class ContextAwareProcessor:
    """Processes user input with context awareness and multi-intent handling"""
    
    def __init__(self):
        self.intent_classifier = IntentClassifier()
        self.entity_extractor = AdvancedEntityExtractor()
    
    def process_complex_input(self, user_input: str, context: Dict = None) -> Dict[str, Any]:
        """Process complex user input and return structured actions"""
        if context is None:
            context = {}
        
        # Classify intents
        intents = self.intent_classifier.classify_intent(user_input)
        
        # Extract entities
        dates = self.entity_extractor.extract_dates(user_input)
        times = self.entity_extractor.extract_times(user_input)
        amounts = self.entity_extractor.extract_amounts(user_input)
        priority = self.entity_extractor.extract_priority(user_input)
        
        # Build structured response
        result = {
            'intents': intents,
            'entities': {
                'dates': dates,
                'times': times,
                'amounts': amounts,
                'priority': priority
            },
            'actions': [],
            'confidence': self._calculate_confidence(intents, user_input)
        }
        
        # Generate specific actions based on intents
        for intent in intents:
            actions = self._generate_actions_for_intent(intent, user_input, result['entities'], context)
            result['actions'].extend(actions)
        
        return result
    
    def _calculate_confidence(self, intents: List[str], text: str) -> float:
        """Calculate confidence score for intent classification"""
        if not intents or 'conversation' in intents:
            return 0.6
        
        # Higher confidence for specific intents with clear patterns
        specific_intents = [i for i in intents if i != 'conversation']
        if len(specific_intents) >= 2:
            return 0.9  # Multiple specific intents = high confidence
        elif len(specific_intents) == 1:
            return 0.8  # Single specific intent = good confidence
        else:
            return 0.6  # Default confidence
    
    def _generate_actions_for_intent(self, intent: str, text: str, entities: Dict, context: Dict) -> List[Dict]:
        """Generate specific actions based on intent and entities"""
        actions = []
        
        if intent == 'task_management':
            actions.extend(self._generate_task_actions(text, entities, context))
        elif intent == 'budget_management':
            actions.extend(self._generate_budget_actions(text, entities, context))
        elif intent == 'schedule_management':
            actions.extend(self._generate_schedule_actions(text, entities, context))
        elif intent == 'information_query':
            actions.extend(self._generate_query_actions(text, entities, context))
        
        return actions
    
    def _generate_task_actions(self, text: str, entities: Dict, context: Dict) -> List[Dict]:
        """Generate task-related actions"""
        actions = []
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['add', 'create', 'new', 'make']):
            action = {
                'type': 'create_task',
                'data': {
                    'task': self._extract_task_description(text),
                    'priority': entities['priority'],
                    'deadline': entities['dates'][0] if entities['dates'] else None,
                    'category': self._infer_category(text)
                }
            }
            actions.append(action)
        
        elif any(word in text_lower for word in ['complete', 'finish', 'done', 'mark']):
            actions.append({
                'type': 'complete_task',
                'data': {'task_query': text}
            })
        
        elif any(word in text_lower for word in ['show', 'list', 'view']):
            actions.append({
                'type': 'list_tasks',
                'data': {'filter': self._extract_task_filter(text)}
            })
        
        return actions
    
    def _generate_budget_actions(self, text: str, entities: Dict, context: Dict) -> List[Dict]:
        """Generate budget-related actions"""
        actions = []
        text_lower = text.lower()
        
        if entities['amounts'] and any(word in text_lower for word in ['spent', 'spend', 'cost', 'paid', 'pay']):
            actions.append({
                'type': 'add_expense',
                'data': {
                    'amount': entities['amounts'][0],
                    'description': self._extract_expense_description(text),
                    'category': self._infer_expense_category(text),
                    'date': entities['dates'][0] if entities['dates'] else datetime.now().strftime('%Y-%m-%d')
                }
            })
        
        elif entities['amounts'] and any(word in text_lower for word in ['earned', 'income', 'salary', 'received']):
            actions.append({
                'type': 'add_income',
                'data': {
                    'amount': entities['amounts'][0],
                    'description': self._extract_income_description(text),
                    'date': entities['dates'][0] if entities['dates'] else datetime.now().strftime('%Y-%m-%d')
                }
            })
        
        elif any(word in text_lower for word in ['show', 'view', 'check', 'summary']):
            actions.append({
                'type': 'show_budget_summary',
                'data': {}
            })
        
        return actions
    
    def _generate_schedule_actions(self, text: str, entities: Dict, context: Dict) -> List[Dict]:
        """Generate schedule-related actions"""
        actions = []
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['schedule', 'book', 'plan', 'appointment', 'meeting']):
            actions.append({
                'type': 'create_event',
                'data': {
                    'title': self._extract_event_title(text),
                    'start_time': self._combine_date_time(entities['dates'], entities['times']),
                    'description': text,
                    'location': self._extract_location(text)
                }
            })
        
        elif any(word in text_lower for word in ['remind', 'reminder']):
            actions.append({
                'type': 'set_reminder',
                'data': {
                    'title': self._extract_reminder_title(text),
                    'time': self._combine_date_time(entities['dates'], entities['times']),
                    'description': text
                }
            })
        
        return actions
    
    def _generate_query_actions(self, text: str, entities: Dict, context: Dict) -> List[Dict]:
        """Generate information query actions"""
        actions = []
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['status', 'summary', 'overview', 'report']):
            actions.append({
                'type': 'generate_summary',
                'data': {'query': text}
            })
        
        return actions
    
    # Helper methods for extracting specific information
    def _extract_task_description(self, text: str) -> str:
        """Extract the main task description from text"""
        # Remove common task creation words
        cleaned = re.sub(r'\b(add|create|new|make|task|todo|reminder)\b', '', text, flags=re.IGNORECASE)
        cleaned = re.sub(r'\b(urgent|important|high|low|priority)\b', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\b(today|tomorrow|next\s+week|by\s+\w+)\b', '', cleaned, flags=re.IGNORECASE)
        return cleaned.strip()
    
    def _extract_expense_description(self, text: str) -> str:
        """Extract expense description from text"""
        # Remove amount and common expense words
        cleaned = re.sub(r'\$\d+(\.\d{2})?', '', text)
        cleaned = re.sub(r'\b(spent|spend|cost|paid|pay|for|on)\b', '', cleaned, flags=re.IGNORECASE)
        return cleaned.strip()
    
    def _extract_income_description(self, text: str) -> str:
        """Extract income description from text"""
        cleaned = re.sub(r'\$\d+(\.\d{2})?', '', text)
        cleaned = re.sub(r'\b(earned|income|salary|received|from)\b', '', cleaned, flags=re.IGNORECASE)
        return cleaned.strip()
    
    def _extract_event_title(self, text: str) -> str:
        """Extract event title from text"""
        cleaned = re.sub(r'\b(schedule|book|plan|appointment|meeting|event)\b', '', text, flags=re.IGNORECASE)
        cleaned = re.sub(r'\b(at|on|from|until)\s+\d{1,2}(:\d{2})?\s*(am|pm)?\b', '', cleaned, flags=re.IGNORECASE)
        return cleaned.strip()
    
    def _extract_reminder_title(self, text: str) -> str:
        """Extract reminder title from text"""
        cleaned = re.sub(r'\b(remind|reminder|me|to)\b', '', text, flags=re.IGNORECASE)
        return cleaned.strip()
    
    def _extract_location(self, text: str) -> str:
        """Extract location from text"""
        location_match = re.search(r'\b(at|in|@)\s+([^,\n]+)', text, re.IGNORECASE)
        return location_match.group(2).strip() if location_match else ""
    
    def _infer_category(self, text: str) -> str:
        """Infer task category from text content"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['work', 'office', 'meeting', 'project', 'deadline']):
            return 'Work'
        elif any(word in text_lower for word in ['doctor', 'gym', 'exercise', 'health', 'medicine']):
            return 'Health'
        elif any(word in text_lower for word in ['learn', 'study', 'course', 'book', 'research']):
            return 'Learning'
        elif any(word in text_lower for word in ['bill', 'payment', 'bank', 'money', 'budget']):
            return 'Finance'
        else:
            return 'Personal'
    
    def _infer_expense_category(self, text: str) -> str:
        """Infer expense category from text content"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['food', 'restaurant', 'lunch', 'dinner', 'coffee', 'grocery']):
            return 'Food'
        elif any(word in text_lower for word in ['gas', 'uber', 'taxi', 'bus', 'train', 'transport']):
            return 'Transport'
        elif any(word in text_lower for word in ['movie', 'game', 'entertainment', 'concert', 'show']):
            return 'Entertainment'
        elif any(word in text_lower for word in ['electric', 'water', 'internet', 'phone', 'utility']):
            return 'Utilities'
        elif any(word in text_lower for word in ['doctor', 'medicine', 'pharmacy', 'health']):
            return 'Healthcare'
        else:
            return 'Other'
    
    def _extract_task_filter(self, text: str) -> str:
        """Extract task filter criteria from text"""
        text_lower = text.lower()
        
        if 'urgent' in text_lower or 'high priority' in text_lower:
            return 'high_priority'
        elif 'today' in text_lower:
            return 'today'
        elif 'overdue' in text_lower:
            return 'overdue'
        else:
            return 'all'
    
    def _combine_date_time(self, dates: List[str], times: List[str]) -> str:
        """Combine date and time into datetime string"""
        if not dates and not times:
            return None
        
        date_str = dates[0] if dates else datetime.now().strftime('%Y-%m-%d')
        time_str = times[0] if times else "09:00"
        
        # Normalize time format
        if 'am' in time_str.lower() or 'pm' in time_str.lower():
            time_str = time_str.lower()
        else:
            time_str += ":00"
        
        try:
            # Try to parse and format properly
            if 'am' in time_str or 'pm' in time_str:
                time_obj = datetime.strptime(time_str, '%I:%M %p' if ':' in time_str else '%I %p')
                time_str = time_obj.strftime('%H:%M')
            
            return f"{date_str} {time_str}"
        except:
            return f"{date_str} 09:00"

# Global instance for easy access
enhanced_nlu = ContextAwareProcessor()

def process_user_input(user_input: str, context: Dict = None) -> Dict[str, Any]:
    """Main function to process user input with enhanced NLU"""
    return enhanced_nlu.process_complex_input(user_input, context)

def get_smart_suggestions(context: Dict = None) -> List[str]:
    """Generate smart suggestions based on current context"""
    suggestions = []
    
    if context is None:
        context = {}
    
    # Import here to avoid circular imports
    try:
        from shared import tasks, budget_entries, schedule_events, get_upcoming_events
        
        # Task-based suggestions
        pending_tasks = [t for t in tasks if not t.get('done', False)]
        overdue_tasks = []
        
        for task in pending_tasks:
            if task.get('deadline'):
                try:
                    deadline = datetime.strptime(task['deadline'], '%Y-%m-%d')
                    if deadline < datetime.now():
                        overdue_tasks.append(task)
                except:
                    pass
        
        if overdue_tasks:
            suggestions.append(f"You have {len(overdue_tasks)} overdue tasks. Would you like to review them?")
        
        if len(pending_tasks) > 10:
            suggestions.append("You have many pending tasks. Consider prioritizing or breaking them down.")
        
        # Budget-based suggestions
        if budget_entries:
            from shared import get_budget_summary
            summary = get_budget_summary()
            
            if summary['balance'] < 0:
                suggestions.append(f"Your budget is ${abs(summary['balance']):.2f} over. Consider reviewing expenses.")
            
            if summary['total_expenses'] > summary['total_income'] * 0.8:
                suggestions.append("You're spending close to your income limit. Track expenses carefully.")
        
        # Schedule-based suggestions
        upcoming = get_upcoming_events(1)  # Next 24 hours
        if upcoming:
            suggestions.append(f"You have {len(upcoming)} events coming up today. Need any preparation reminders?")
        
        # Time-based suggestions
        current_hour = datetime.now().hour
        if 9 <= current_hour <= 11:
            suggestions.append("Good morning! Ready to tackle today's priorities?")
        elif 13 <= current_hour <= 14:
            suggestions.append("Afternoon check-in: How are your tasks progressing?")
        elif 17 <= current_hour <= 19:
            suggestions.append("End of day: Want to review what you accomplished?")
    
    except ImportError:
        pass
    
    return suggestions[:3]  # Return top 3 suggestions