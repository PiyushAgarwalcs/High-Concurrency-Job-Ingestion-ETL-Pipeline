"""
Comprehensive Unit and Regression Tests for the Upgraded FilterEngine.

Validates:
- 4-tier Role Classification and Priority Mapping
- Specific title precedence over generic titles
- Negative role exclusions and exception handling
- Experience boundaries (0-2 years, ranges, months, company history guards)
- Indian location eligibility and foreign exclusions
- Salary extraction (decimals, ranges, INR annualization, monthly stipends, LinkedIn floor)
- SDE AI/DSA relevance validation
- Auditable explainable rejection reasons and aggregate statistics
- Non-mutation and backwards compatibility
"""

import pytest
from core.models import JobListing
from core.filter_engine import FilterEngine
from config.role_categories import (
    CATEGORY_CORE_AI_FDE,
    CATEGORY_ML_SPECIALIZED_AI,
    CATEGORY_DATA_SCIENCE_APPLIED_RESEARCH,
    CATEGORY_AI_RELATED_SOFTWARE_ENGINEERING,
)


@pytest.fixture
def filter_engine():
    return FilterEngine()


def _make_job(
    title: str = "AI Engineer",
    company: str = "Test Co",
    location: str = "Bangalore",
    desc: str = "Building generative AI and LLM agents using Python and PyTorch",
    exp: str = "0-1 years",
    source: str = "greenhouse",
    salary_lpa: float = None,
    salary_str: str = None,
) -> JobListing:
    return JobListing(
        company_name=company,
        job_title=title,
        location=location,
        apply_url="https://example.com/apply/1",
        source_platform=source,
        job_description_summary=desc,
        experience_required=exp,
        estimated_salary_lpa=salary_lpa,
        salary=salary_str,
    )


# ─── 1. Role Classification Tests ──────────────────────────────────────────────

class TestRoleClassification:
    def test_priority_1_core_ai_roles(self, filter_engine):
        ai_job = _make_job(title="AI Engineer")
        assert filter_engine._get_role_priority(ai_job) == 1
        cat, prio, matched, _ = filter_engine._classify_role(ai_job)
        assert prio == 1
        assert cat == CATEGORY_CORE_AI_FDE
        assert "ai engineer" in matched

        applied_ai = _make_job(title="Applied AI Engineer")
        assert filter_engine._get_role_priority(applied_ai) == 1

        genai_job = _make_job(title="Generative AI Engineer")
        assert filter_engine._get_role_priority(genai_job) == 1

        agentic_job = _make_job(title="Agentic AI Engineer")
        assert filter_engine._get_role_priority(agentic_job) == 1

        llm_job = _make_job(title="LLM Engineer")
        assert filter_engine._get_role_priority(llm_job) == 1

    def test_priority_1_forward_deployed_roles(self, filter_engine):
        fde_job = _make_job(title="Forward Deployed Engineer")
        assert filter_engine._get_role_priority(fde_job) == 1
        cat, prio, _, _ = filter_engine._classify_role(fde_job)
        assert prio == 1
        assert cat == CATEGORY_CORE_AI_FDE

        fde_ai_job = _make_job(title="Forward Deployed AI Engineer")
        assert filter_engine._get_role_priority(fde_ai_job) == 1

        fde_swe_job = _make_job(title="Forward Deployed Software Engineer")
        assert filter_engine._get_role_priority(fde_swe_job) == 1

        # Standalone FDE abbreviation with deployment/AI context
        fde_abbrev_job = _make_job(
            title="FDE - Early Career",
            desc="Deploying client-facing AI integration pipelines."
        )
        assert filter_engine._get_role_priority(fde_abbrev_job) == 1

    def test_priority_2_ml_and_specialized_ai(self, filter_engine):
        ml_job = _make_job(title="Machine Learning Engineer")
        assert filter_engine._get_role_priority(ml_job) == 2
        cat, prio, _, _ = filter_engine._classify_role(ml_job)
        assert prio == 2
        assert cat == CATEGORY_ML_SPECIALIZED_AI

        ml_short = _make_job(title="ML Engineer")
        assert filter_engine._get_role_priority(ml_short) == 2

        nlp_job = _make_job(title="NLP Engineer")
        assert filter_engine._get_role_priority(nlp_job) == 2

        cv_job = _make_job(title="Computer Vision Engineer")
        assert filter_engine._get_role_priority(cv_job) == 2

        deep_job = _make_job(title="Deep Learning Engineer")
        assert filter_engine._get_role_priority(deep_job) == 2

    def test_priority_3_data_science_and_applied_research(self, filter_engine):
        ds_job = _make_job(title="Data Scientist")
        assert filter_engine._get_role_priority(ds_job) == 3
        cat, prio, _, _ = filter_engine._classify_role(ds_job)
        assert prio == 3
        assert cat == CATEGORY_DATA_SCIENCE_APPLIED_RESEARCH

        data_eng_job = _make_job(title="Data Engineer")
        assert filter_engine._get_role_priority(data_eng_job) == 3

    def test_priority_4_ai_related_software_engineering(self, filter_engine):
        backend_job = _make_job(title="Backend Engineer")
        assert filter_engine._get_role_priority(backend_job) == 4
        cat, prio, _, _ = filter_engine._classify_role(backend_job)
        assert prio == 4
        assert cat == CATEGORY_AI_RELATED_SOFTWARE_ENGINEERING

        sde_job = _make_job(title="Software Development Engineer")
        assert filter_engine._get_role_priority(sde_job) == 4

        sde_1_job = _make_job(title="SDE I")
        assert filter_engine._get_role_priority(sde_1_job) == 4

        swe_job = _make_job(title="SWE")
        assert filter_engine._get_role_priority(swe_job) == 4

    def test_specific_titles_precede_generic_titles(self, filter_engine):
        # AI Software Engineer should be Priority 1, NOT Priority 4 Software Engineer
        ai_swe = _make_job(title="AI Software Engineer")
        assert filter_engine._get_role_priority(ai_swe) == 1

        # Forward Deployed Software Engineer should be Priority 1, NOT Priority 4 Software Engineer
        fde_swe = _make_job(title="Forward Deployed Software Engineer")
        assert filter_engine._get_role_priority(fde_swe) == 1

        # AI Platform Engineer should be Priority 2, NOT Priority 4 Platform Engineer
        ai_plat = _make_job(title="AI Platform Engineer")
        assert filter_engine._get_role_priority(ai_plat) == 2

    def test_irrelevant_roles_return_none(self, filter_engine):
        sales_job = _make_job(title="Account Executive")
        assert filter_engine._get_role_priority(sales_job) is None

        hr_job = _make_job(title="HR Generalist")
        assert filter_engine._get_role_priority(hr_job) is None


# ─── 2. Negative Role Tests ───────────────────────────────────────────────────

class TestNegativeRoles:
    def test_rejects_senior_roles(self, filter_engine):
        senior_ai = _make_job(title="Senior AI Engineer")
        assert filter_engine._has_negative_role(senior_ai) is True

        lead_ai = _make_job(title="Lead Machine Learning Engineer")
        assert filter_engine._has_negative_role(lead_ai) is True

        staff_ml = _make_job(title="Staff ML Engineer")
        assert filter_engine._has_negative_role(staff_ml) is True

        principal_ai = _make_job(title="Principal AI Scientist")
        assert filter_engine._has_negative_role(principal_ai) is True

    def test_rejects_frontend_and_fullstack(self, filter_engine):
        fe = _make_job(title="Frontend Developer")
        assert filter_engine._has_negative_role(fe) is True

        fs = _make_job(title="Full Stack Engineer")
        assert filter_engine._has_negative_role(fs) is True

        react_dev = _make_job(title="React Developer")
        assert filter_engine._has_negative_role(react_dev) is True

    def test_rejects_qa_and_devops(self, filter_engine):
        qa = _make_job(title="QA Engineer")
        assert filter_engine._has_negative_role(qa) is True

        devops = _make_job(title="DevOps Engineer")
        assert filter_engine._has_negative_role(devops) is True

    def test_exceptions_for_ai_roles_with_supporting_skills(self, filter_engine):
        # AI Engineer requiring knowledge of React should NOT be rejected
        ai_with_react = _make_job(
            title="AI Engineer",
            desc="Building LLM user interfaces; familiarity with React and FastAPI is a plus."
        )
        assert filter_engine._has_negative_role(ai_with_react) is False
        eval_res = filter_engine.evaluate_job(ai_with_react)
        assert eval_res["accepted"] is True

        # AI Platform Engineer mentioning cloud infrastructure should NOT be rejected
        ai_platform = _make_job(
            title="AI Platform Engineer",
            desc="Developing model training infrastructure across AWS cloud and Kubernetes."
        )
        assert filter_engine._has_negative_role(ai_platform) is False
        eval_res = filter_engine.evaluate_job(ai_platform)
        assert eval_res["accepted"] is True

        # Forward Deployed Engineer mentioning customer interaction should NOT be rejected
        fde_customer = _make_job(
            title="Forward Deployed Engineer",
            desc="Collaborate directly with enterprise customer stakeholders to deploy AI agents."
        )
        assert filter_engine._has_negative_role(fde_customer) is False
        eval_res = filter_engine.evaluate_job(fde_customer)
        assert eval_res["accepted"] is True

        # AI Engineer working with DevOps tools should NOT be rejected
        ai_devops = _make_job(
            title="AI Engineer",
            desc="Working closely with devops pipelines, Docker containers, and CI/CD."
        )
        assert filter_engine._has_negative_role(ai_devops) is False
        eval_res = filter_engine.evaluate_job(ai_devops)
        assert eval_res["accepted"] is True


# ─── 3. SDE Validation & AI Relevance Tests ───────────────────────────────────

class TestSdeValidation:
    def test_generic_sde_rejected_without_ai_or_dsa(self, filter_engine):
        plain_sde = _make_job(
            title="Software Engineer",
            desc="Managing customer relations, invoice database, and billing paperwork."
        )
        assert filter_engine._is_generic_sde(plain_sde) is True
        assert filter_engine._has_sde_validation(plain_sde) is False
        eval_res = filter_engine.evaluate_job(plain_sde)
        assert eval_res["accepted"] is False
        assert eval_res["rejection_reason"] == "generic_sde_missing_ai_dsa_context"

    def test_python_alone_does_not_qualify_generic_sde(self, filter_engine):
        python_only_sde = _make_job(
            title="Python Developer",
            desc="Writing Python scripts to parse CSV files and generate reports."
        )
        assert filter_engine._has_sde_validation(python_only_sde) is False
        eval_res = filter_engine.evaluate_job(python_only_sde)
        assert eval_res["accepted"] is False

    def test_generic_sde_accepted_with_dsa(self, filter_engine):
        dsa_sde = _make_job(
            title="Software Development Engineer",
            desc="Design high-performance systems requiring strong foundations in data structures and algorithms."
        )
        assert filter_engine._is_generic_sde(dsa_sde) is True
        assert filter_engine._has_sde_validation(dsa_sde) is True
        eval_res = filter_engine.evaluate_job(dsa_sde)
        assert eval_res["accepted"] is True
        assert eval_res["role_priority"] == 4

    def test_generic_sde_accepted_with_ai_ml(self, filter_engine):
        ai_sde = _make_job(
            title="Software Engineer",
            desc="Developing model deployment services and integrating large language models with REST APIs."
        )
        assert filter_engine._is_generic_sde(ai_sde) is True
        assert filter_engine._has_sde_validation(ai_sde) is True
        eval_res = filter_engine.evaluate_job(ai_sde)
        assert eval_res["accepted"] is True


# ─── 4. Experience Filtering Tests ────────────────────────────────────────────

class TestExperienceFiltering:
    def test_accepts_valid_fresher_and_early_career(self, filter_engine):
        assert filter_engine._exceeds_experience(_make_job(exp="Fresher")) is False
        assert filter_engine._exceeds_experience(_make_job(exp="0-1 years")) is False
        assert filter_engine._exceeds_experience(_make_job(exp="1-2 years")) is False
        assert filter_engine._exceeds_experience(_make_job(exp="0-2 years")) is False
        assert filter_engine._exceeds_experience(_make_job(exp="24 months")) is False
        assert filter_engine._exceeds_experience(_make_job(exp="1 year")) is False
        assert filter_engine._exceeds_experience(_make_job(exp="2 years")) is False

    def test_rejects_exceeding_experience(self, filter_engine):
        # 3+ years rejected
        assert filter_engine._exceeds_experience(_make_job(exp="3+ years")) is True

        # At least 3 years rejected
        assert filter_engine._exceeds_experience(_make_job(exp="At least 3 years")) is True

        # Upper bound of 1-3 years is 3 > 2 -> rejected
        assert filter_engine._exceeds_experience(_make_job(exp="1-3 years")) is True

        # Upper bound of 2-4 years is 4 > 2 -> rejected
        assert filter_engine._exceeds_experience(_make_job(exp="2-4 years")) is True

    def test_unknown_experience_allowed(self, filter_engine):
        job = _make_job(exp=None, desc="Join our fast-growing startup to build AI products.")
        eval_res = filter_engine._evaluate_experience(job)
        assert eval_res["experience_match"] is True
        assert eval_res["experience_confidence"] == "unknown"

    def test_company_experience_false_positive_guard(self, filter_engine):
        # Description mentions company experience, but candidate is fresher
        job = _make_job(
            exp="0-1 years",
            desc="Our engineering team has 5+ years of experience delivering enterprise AI. Candidate requirements: 0-1 years."
        )
        assert filter_engine._exceeds_experience(job) is False

        # Company history in description without structured exp field
        job_no_exp = _make_job(
            exp=None,
            desc="With over 10 years of experience in financial services, we are seeking entry-level graduates."
        )
        assert filter_engine._exceeds_experience(job_no_exp) is False

    def test_technology_version_false_positive_guard(self, filter_engine):
        # 'Python 3+' in description should not trigger 3+ years experience rejection
        job = _make_job(
            exp="Fresher",
            desc="Must be proficient with Python 3+ and PyTorch."
        )
        assert filter_engine._exceeds_experience(job) is False


# ─── 5. Location Filtering Tests ──────────────────────────────────────────────

class TestLocationFiltering:
    def test_accepts_bangalore_and_indian_cities(self, filter_engine):
        assert filter_engine._is_acceptable_location(_make_job(location="Bangalore")) is True
        assert filter_engine._is_acceptable_location(_make_job(location="Bengaluru")) is True
        assert filter_engine._is_acceptable_location(_make_job(location="Chennai")) is True
        assert filter_engine._is_acceptable_location(_make_job(location="Hyderabad")) is True
        assert filter_engine._is_acceptable_location(_make_job(location="Kochi")) is True
        assert filter_engine._is_acceptable_location(_make_job(location="Ahmedabad")) is True
        assert filter_engine._is_acceptable_location(_make_job(location="Hybrid Bangalore")) is True

    def test_accepts_remote_india_and_generic_remote(self, filter_engine):
        assert filter_engine._is_acceptable_location(_make_job(location="India Remote")) is True
        assert filter_engine._is_acceptable_location(_make_job(location="Remote India")) is True
        assert filter_engine._is_acceptable_location(_make_job(location="Remote")) is True

    def test_rejects_foreign_locations(self, filter_engine):
        assert filter_engine._is_acceptable_location(_make_job(location="San Francisco, USA")) is False
        assert filter_engine._is_acceptable_location(_make_job(location="London, UK")) is False
        assert filter_engine._is_acceptable_location(_make_job(location="Berlin, Germany")) is False

    def test_foreign_restricted_remote_rejected(self, filter_engine):
        restricted_remote = _make_job(
            location="Remote",
            desc="Must be legally authorized to work in the US without sponsorship."
        )
        assert filter_engine._is_acceptable_location(restricted_remote) is False

    def test_unknown_location_allowed(self, filter_engine):
        assert filter_engine._is_acceptable_location(_make_job(location="")) is True
        assert filter_engine._is_acceptable_location(_make_job(location="Not specified")) is True


# ─── 6. Salary Extraction and Floor Tests ─────────────────────────────────────

class TestSalaryExtractionAndFloor:
    def test_extract_exact_lpa_and_decimals(self, filter_engine):
        job_12 = _make_job(desc="Compensation is 12 LPA CTC.")
        filter_engine._extract_salary(job_12)
        assert job_12.estimated_salary_lpa == 12.0

        job_12_5 = _make_job(desc="Package: 12.5 LPA fixed.")
        filter_engine._extract_salary(job_12_5)
        assert job_12_5.estimated_salary_lpa == 12.5

    def test_extract_salary_ranges(self, filter_engine):
        job_range = _make_job(desc="Salary range: 12-18 LPA.")
        filter_engine._extract_salary(job_range)
        assert job_range.min_salary_lpa == 12.0
        assert job_range.max_salary_lpa == 18.0

    def test_extract_annual_inr(self, filter_engine):
        job_inr = _make_job(desc="Salary: ₹15,00,000 per annum.")
        filter_engine._extract_salary(job_inr)
        assert job_inr.estimated_salary_lpa == 15.0

        job_inr_word = _make_job(desc="Compensation: 20 Lakhs per annum.")
        filter_engine._extract_salary(job_inr_word)
        assert job_inr_word.estimated_salary_lpa == 20.0

    def test_extract_monthly_stipend(self, filter_engine):
        job_stipend = _make_job(desc="Monthly stipend: ₹25,000 / month.")
        filter_engine._extract_salary(job_stipend)
        # 25,000 * 12 = 300,000 = 3.0 LPA
        assert job_stipend.estimated_salary_lpa == 3.0

    def test_linkedin_floor_enforcement(self, filter_engine):
        # Below floor (8 LPA) on LinkedIn Easy Apply -> rejected
        low_job = _make_job(source="linkedin_easy_apply", salary_lpa=8.0)
        eval_low = filter_engine.evaluate_job(low_job)
        assert eval_low["accepted"] is False
        assert eval_low["rejection_reason"] == "salary_below_floor"

        # Above floor (15-20 LPA) on LinkedIn Easy Apply -> accepted
        high_job = _make_job(
            source="linkedin_easy_apply",
            desc="Offering 15-20 LPA for entry-level AI engineers."
        )
        eval_high = filter_engine.evaluate_job(high_job)
        assert eval_high["accepted"] is True

        # Crossing floor (8-15 LPA) on LinkedIn Easy Apply -> allowed (uncertain range)
        cross_job = _make_job(
            source="linkedin_easy_apply",
            desc="Salary band: 8-15 LPA based on evaluation."
        )
        eval_cross = filter_engine.evaluate_job(cross_job)
        assert eval_cross["accepted"] is True
        assert eval_cross["salary_eligibility"] == "uncertain_range"

        # Undisclosed salary on LinkedIn Easy Apply -> allowed
        undisclosed_job = _make_job(source="linkedin_easy_apply", salary_lpa=None, desc="Competitive package.")
        eval_undisc = filter_engine.evaluate_job(undisclosed_job)
        assert eval_undisc["accepted"] is True


# ─── 7. Auditability and Pipeline Integration Tests ───────────────────────────

class TestAuditabilityAndIntegration:
    def test_structured_decision_on_filtered_jobs(self, filter_engine):
        jobs = [
            # Reject: senior
            _make_job(title="Senior AI Engineer"),
            # Reject: frontend
            _make_job(title="Frontend Developer"),
            # Reject: generic SDE no AI
            _make_job(title="Software Engineer", desc="Invoice records admin"),
            # Reject: exp > 2
            _make_job(title="AI Engineer", exp="4+ years"),
            # Reject: foreign
            _make_job(title="AI Engineer", location="London, UK"),
            # Reject: salary < 12
            _make_job(title="AI Engineer", source="linkedin_easy_apply", salary_lpa=8),
            # Accept: P1
            _make_job(title="Forward Deployed Engineer"),
            # Accept: P2
            _make_job(title="Machine Learning Engineer"),
            # Accept: P3
            _make_job(title="Data Scientist"),
            # Accept: P4
            _make_job(title="Software Engineer", desc="Algorithms, data structures and python"),
        ]

        accepted = filter_engine.filter_jobs(jobs)
        assert len(accepted) == 4

        # Check priorities on accepted jobs
        assert accepted[0].role_priority == 1
        assert accepted[1].role_priority == 2
        assert accepted[2].role_priority == 3
        assert accepted[3].role_priority == 4

        # Verify aggregate stats
        stats = filter_engine.get_statistics()
        assert stats["total_processed"] == 10
        assert stats["accepted"] == 4
        assert stats["rejected"] == 6
        assert stats["rejections_by_stage"]["role_filter"] >= 2
        assert stats["rejections_by_stage"]["relevance_filter"] >= 1
        assert stats["rejections_by_stage"]["experience_filter"] >= 1
        assert stats["rejections_by_stage"]["location_filter"] >= 1
        assert stats["rejections_by_stage"]["salary_filter"] >= 1

    def test_generic_software_engineer_classification(self, filter_engine):
        generic_swe = _make_job(
            title="Generic Software Engineer",
            desc="Building high-throughput services using distributed systems, python, and algorithms."
        )
        assert filter_engine._get_role_priority(generic_swe) == 4
        decision = filter_engine.evaluate_job(generic_swe)
        assert decision["accepted"] is True
        assert decision["role_priority"] == 4

    def test_non_mutation_of_source_data(self, filter_engine):
        original_title = "Forward Deployed AI Engineer"
        original_company = "Palantir India"
        original_url = "https://example.com/apply/fde-101"
        original_location = "Bengaluru, Karnataka"

        job = _make_job(
            title=original_title,
            company=original_company,
            location=original_location,
        )
        job.apply_url = original_url

        filter_engine.filter_jobs([job])

        assert job.job_title == original_title
        assert job.company_name == original_company
        assert job.apply_url == original_url
        assert job.location == original_location

    def test_integration_with_ranking_engine(self, filter_engine):
        from core.ranking_engine import RankingEngine
        jobs = [
            _make_job(title="AI Engineer", salary_lpa=18.0, desc="LLM PyTorch"),
            _make_job(title="Data Scientist", salary_lpa=14.0, desc="Pandas SQL"),
            _make_job(title="Backend Engineer", salary_lpa=12.0, desc="Algorithms DSA Python"),
        ]

        filtered = filter_engine.filter_jobs(jobs)
        assert len(filtered) == 3

        ranking_engine = RankingEngine()
        ranked = ranking_engine.rank_jobs(filtered)
        assert len(ranked) == 3
        # AI Engineer (P1, 18 LPA) should rank higher than Backend Engineer (P4)
        assert ranked[0].job_title == "AI Engineer"
        assert ranked[0].rank_score > ranked[-1].rank_score

    def test_job_listing_db_safe_serialization(self, filter_engine):
        job = _make_job(title="AI Engineer", salary_lpa=15.0)
        filter_engine.filter_jobs([job])

        db_dict = job.to_dict(db_safe=True)
        # Should not include non-table fields like filtering_decision in db_safe mode
        assert "filtering_decision" not in db_dict
        assert "job_id" in db_dict
        assert "role_priority" in db_dict
        assert db_dict["role_priority"] == 1

        full_dict = job.to_dict(db_safe=False)
        assert "filtering_decision" in full_dict

    def test_search_terms_backward_compatibility(self):
        import config.search_terms as st
        assert len(st.PRIORITY_1_ROLES) > 0
        assert len(st.PRIORITY_2_ROLES) > 0
        assert len(st.PRIORITY_3_ROLES) > 0
        assert len(st.PRIORITY_4_ROLES) > 0
        assert len(st.ALL_ROLE_KEYWORDS) > 0
        assert len(st.SDE_VALIDATION_KEYWORDS) > 0
        assert len(st.SDE_TITLE_KEYWORDS) > 0
        assert len(st.SEARCH_QUERIES) > 0
        assert len(st.ATS_TITLE_KEYWORDS) > 0
        assert len(st.ACCEPT_EXPERIENCE_KEYWORDS) > 0
        assert len(st.REJECT_EXPERIENCE_KEYWORDS) > 0
        assert len(st.PRIMARY_LOCATIONS) > 0
        assert len(st.ALL_ACCEPTED_LOCATIONS) > 0
        assert len(st.NEGATIVE_TITLE_KEYWORDS) > 0
        assert len(st.DESIRED_SKILLS) > 0
