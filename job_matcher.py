import re
import json
from typing import List, Dict, Optional
import aiohttp
from datetime import datetime
import asyncio

class JobMatcher:
    """AI-powered job matcher with resume analysis"""
    
    def __init__(self, ai_client=None):
        self.ai_client = ai_client
        self.hh_api_url = 'https://api.hh.ru/vacancies'
        self.cache = {}
        
    async def search_matching_jobs(self, query: str, resume_text: str, filters: Dict) -> List[Dict]:
        """
        Search and match jobs with resume using AI
        """
        # Get vacancies from hh.ru
        vacancies = await self._fetch_vacancies(query, filters)
        
        if not vacancies:
            return []
        
        # Match each vacancy with resume
        matched_jobs = []
        for vac in vacancies:
            match_score = await self._calculate_match(vac, resume_text)
            if match_score >= 60:  # Threshold 60%
                match_reason = await self._get_match_reason(vac, resume_text)
                matched_jobs.append({
                    **vac,
                    'match_score': match_score,
                    'match_reason': match_reason,
                    'skills_match': await self._get_skills_match(vac, resume_text)
                })
        
        # Sort by match score
        matched_jobs.sort(key=lambda x: x['match_score'], reverse=True)
        return matched_jobs
    
    async def _fetch_vacancies(self, query: str, filters: Dict) -> List[Dict]:
        """Fetch vacancies from hh.ru API"""
        params = {
            'text': query,
            'per_page': 30,
            'search_field': 'name',
            'area': 1,  # Russia
            'only_with_salary': False
        }
        
        if filters.get('remote_only'):
            params['schedule'] = 'remote'
        
        if filters.get('experience_level'):
            experience_map = {
                'junior': '1',
                'middle': '2', 
                'senior': '3'
            }
            params['experience'] = experience_map.get(filters['experience_level'], '')
        
        headers = {
            'User-Agent': 'JobApplyBot/1.0 (your_email@example.com)'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.hh_api_url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        vacancies = []
                        
                        for item in data.get('items', []):
                            title = item.get('name', '').lower()
                            
                            # Check exclusions
                            if any(excl.lower() in title for excl in filters.get('exclude_keywords', [])):
                                continue
                            
                            salary = item.get('salary')
                            if salary and salary.get('from'):
                                if salary['from'] < filters.get('min_salary', 0):
                                    continue
                            
                            # Get full description
                            description = await self._get_vacancy_description(item.get('id'))
                            
                            vacancies.append({
                                'id': item.get('id'),
                                'name': item.get('name'),
                                'employer': item.get('employer', {}).get('name'),
                                'area': item.get('area', {}).get('name'),
                                'url': item.get('alternate_url'),
                                'salary': self._format_salary(salary) if salary else 'Зарплата не указана',
                                'description': description,
                                'key_skills': [skill.get('name') for skill in item.get('key_skills', [])],
                                'created_at': item.get('created_at'),
                                'schedule': item.get('schedule', {}).get('name', ''),
                                'experience': item.get('experience', {}).get('name', ''),
                                'site': 'hh.ru'
                            })
                        
                        return vacancies
                    else:
                        print(f"hh.ru API error: {response.status}")
                        return []
        except Exception as e:
            print(f"Error fetching vacancies: {e}")
            return []
    
    async def _get_vacancy_description(self, vacancy_id: str) -> str:
        """Get full vacancy description"""
        cache_key = f"desc_{vacancy_id}"
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.hh_api_url}/{vacancy_id}"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        description = data.get('description', '')[:3000]
                        self.cache[cache_key] = description
                        return description
        except:
            pass
        return ''
    
    async def _calculate_match(self, vacancy: Dict, resume_text: str) -> int:
        """Calculate match percentage using AI"""
        if not self.ai_client:
            return self._simple_match(vacancy, resume_text)
        
        prompt = f"""
Оцени соответствие между резюме и вакансией в процентах (0-100).

Резюме кандидата (ключевые навыки и опыт):
{resume_text[:1000]}

Вакансия:
Название: {vacancy['name']}
Описание: {vacancy.get('description', '')[:1000]}
Требуемые навыки: {', '.join(vacancy.get('key_skills', []))}
Требуемый опыт: {vacancy.get('experience', '')}

Оцени:
1. Соответствие технических навыков (0-40)
2. Соответствие опыта работы (0-30)
3. Соответствие стека технологий (0-30)

Ответь ТОЛЬКО числом от 0 до 100.
"""
        
        try:
            response = await self.ai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.3
            )
            score_text = response.choices[0].message.content.strip()
            numbers = re.findall(r'\d+', score_text)
            if numbers:
                return min(100, int(numbers[0]))
            return 50
        except:
            return self._simple_match(vacancy, resume_text)
    
    def _simple_match(self, vacancy: Dict, resume_text: str) -> int:
        """Simple matching algorithm without AI"""
        score = 0
        total = 0
        resume_lower = resume_text.lower()
        
        # Check skills (40 points)
        skills = vacancy.get('key_skills', [])
        if skills:
            matched = 0
            for skill in skills[:15]:
                if skill.lower() in resume_lower:
                    matched += 1
            score += (matched / max(len(skills[:15]), 1)) * 40
            total += 40
        
        # Check job title (30 points)
        title_words = vacancy['name'].lower().split()
        tech_keywords = ['react', 'javascript', 'typescript', 'python', 'java', 'php', 'vue', 'angular', 'node', 'django', 'flask', 'spring', 'aws', 'docker']
        
        tech_found = 0
        for word in tech_keywords:
            if word in resume_lower and word in vacancy['name'].lower():
                tech_found += 1
        score += min(30, tech_found * 10)
        total += 30
        
        # Check experience level (30 points)
        exp_requirements = vacancy.get('experience', '').lower()
        if 'junior' in exp_requirements and 'junior' in resume_lower:
            score += 25
        elif 'middle' in exp_requirements and 'middle' in resume_lower:
            score += 25
        elif 'senior' in exp_requirements and 'senior' in resume_lower:
            score += 25
        elif 'без опыта' in exp_requirements:
            score += 20
        total += 30
        
        return min(100, int((score / max(total, 1)) * 100))
    
    async def _get_match_reason(self, vacancy: Dict, resume_text: str) -> str:
        """Get AI explanation for match"""
        if not self.ai_client:
            return "Соответствует по ключевым навыкам и опыту"
        
        prompt = f"""
Объясни кратко (1-2 предложения), почему кандидат подходит на эту вакансию.

Резюме: {resume_text[:500]}
Вакансия: {vacancy['name']}
Навыки: {', '.join(vacancy.get('key_skills', []))}

Ответь на русском языке, конкретно и полезно.
"""
        
        try:
            response = await self.ai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.5
            )
            return response.choices[0].message.content.strip()
        except:
            return "Соответствует по ключевым навыкам"
    
    async def _get_skills_match(self, vacancy: Dict, resume_text: str) -> List[str]:
        """Get list of matching skills"""
        resume_skills = self._extract_skills(resume_text)
        required_skills = vacancy.get('key_skills', [])
        
        matched = []
        for skill in required_skills:
            if skill.lower() in resume_text.lower():
                matched.append(skill)
        return matched[:5]
    
    def _extract_skills(self, text: str) -> List[str]:
        """Extract technical skills from text"""
        skills = []
        tech_stack = [
            'react', 'vue', 'angular', 'javascript', 'typescript', 'python',
            'java', 'php', 'node', 'express', 'django', 'flask', 'spring',
            'aws', 'docker', 'kubernetes', 'git', 'linux', 'sql', 'mongodb',
            'postgresql', 'redis', 'graphql', 'rest', 'html', 'css', 'sass'
        ]
        
        for skill in tech_stack:
            if skill in text.lower():
                skills.append(skill)
        return skills
    
    def _format_salary(self, salary: Dict) -> str:
        """Format salary"""
        parts = []
        if salary.get('from'):
            parts.append(f"от {salary['from']:,}".replace(',', ' '))
        if salary.get('to'):
            parts.append(f"до {salary['to']:,}".replace(',', ' '))
        
        if parts:
            result = ' '.join(parts)
            currency = salary.get('currency', '')
            if currency:
                result += f" {currency}"
            return result
        return 'Зарплата не указана'
