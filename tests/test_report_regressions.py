import pytest
from profit_ranker import rank_lead
from freelance_sources import _parse_prolinker_markdown
from browser_apply import _remote_job_challenge_pending, _remote_job_validation_errors


@pytest.mark.parametrize('title', [
    'Looking for a frontend dev with knowledge of MEAN',
    'Resolving issues in MS Access',
    'UI UX designer for a complete dashboard',
    'Magento Developer',
    'Full-time C# developer',
])
def test_report_mismatches_rejected_despite_frontend_description(title):
    lead = {'source': 'prolinker_firecrawl', 'title': title,
            'description': 'React TypeScript frontend HTML CSS landing'}
    assert rank_lead(lead)['eligible'] is False


def test_react_project_remains_eligible():
    assert rank_lead({'source': 'prolinker_firecrawl', 'title': 'React JS developer',
                      'description': 'React TypeScript HTML CSS'})['eligible']


def test_search_card_does_not_borrow_next_projects_skills():
    md = ('[MS Access repair](https://prolinker.com/projects/database/access-ABC12)\nDatabase repair only\n'
          '[React developer](https://prolinker.com/projects/react/website-DEF34)\nReact TypeScript HTML CSS')
    leads = _parse_prolinker_markdown(md)
    assert 'React' not in leads[0]['description']
    assert 'TypeScript' in leads[1]['description']


class Token:
    def __init__(self, value, exists=True):
        self.value, self.exists = value, exists
        self.first = self
    def count(self):
        return int(self.exists)
    def input_value(self):
        return self.value


class Page:
    def __init__(self, token):
        self.token = token
    def locator(self, selector):
        assert selector == 'input[name="add_response[captcha_response]"]'
        return self.token


@pytest.mark.parametrize('value,exists,pending', [('', True, True), ('valid-token', True, False), ('', False, False)])
def test_turnstile_requires_real_token(value, exists, pending):
    assert _remote_job_challenge_pending(Page(Token(value, exists))) is pending


def test_validation_ignores_info_alerts_and_reads_dom_property():
    class Field:
        def is_visible(self, **kwargs): return True
        def evaluate(self, expression):
            assert 'validationMessage' in expression
            return 'Please enter an email address.'
    class Errors:
        def count(self): return 1
        def nth(self, i): return Field()
    class ErrorPage:
        def locator(self, selector):
            assert '[role="alert"]' not in selector
            assert '.alert-danger' in selector
            assert 'form[name="add_response"] input:invalid' in selector
            return Errors()
    assert _remote_job_validation_errors(ErrorPage()) == ['please enter an email address.']
