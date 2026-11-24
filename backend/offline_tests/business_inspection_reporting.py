"""Pure selection/mocked failure tests. No MySQL, Stripe or environment access."""
import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
from unittest import TestCase,main
from unittest.mock import patch

path=Path(__file__).resolve().parents[1]/'scripts/find_viva_billing_business.py'
spec=importlib.util.spec_from_file_location('offline_business_reporting',path)
script=importlib.util.module_from_spec(spec); spec.loader.exec_module(script)


class ReportingTests(TestCase):
    def setUp(self):
        script.RESULT.clear(); script.RESULT.update(script.INITIAL_RESULT)
        script.PHASE='PRECHECK'

    def choose(self,candidates,answers):
        output=io.StringIO()
        with patch('builtins.input',side_effect=answers),redirect_stdout(output):
            code=script.choose_candidate(candidates)
        return code,output.getvalue()

    def test_synthetic_selects_current_verified_candidate(self):
        code,_=self.choose([(7,0)],['SYNTHETIC'])
        self.assertEqual(code,0)
        self.assertEqual(script.RESULT['STEP357_STATUS'],'READY')
        self.assertEqual(script.RESULT['BUSINESS_REFERENCE'],'VIVA-BUSINESS-7')
        self.assertEqual(script.RESULT['EXIT_REASON'],'CANDIDATE_SELECTED_AND_VERIFIED')

    def test_skip_only_candidate_is_explicit_exhaustion_never_selection(self):
        code,output=self.choose([(1,0)],['SKIP'])
        self.assertEqual(code,1)
        self.assertIn('CANDIDATE_OUTCOME=SKIPPED',output)
        self.assertEqual(script.RESULT['SKIPPED_CANDIDATES'],1)
        self.assertEqual(script.RESULT['EXIT_REASON'],'ALL_CANDIDATES_EXHAUSTED')
        self.assertEqual(script.RESULT['ELIGIBLE_BUSINESS_FOUND'],'no')
        self.assertEqual(script.RESULT['BUSINESS_REFERENCE'],'NONE')

    def test_skip_then_synthetic_selects_only_second_candidate(self):
        code,_=self.choose([(1,0),(2,1)],['SKIP','SYNTHETIC'])
        self.assertEqual(code,0)
        self.assertEqual(script.RESULT['BUSINESS_REFERENCE'],'VIVA-BUSINESS-2')
        self.assertEqual(script.RESULT['SKIPPED_CANDIDATES'],1)

    def test_all_skipped_and_no_candidates_have_different_reasons(self):
        self.choose([(1,0),(2,0)],['SKIP','SKIP'])
        self.assertEqual(script.RESULT['EXIT_REASON'],'ALL_CANDIDATES_EXHAUSTED')
        self.assertEqual(script.RESULT['SKIPPED_CANDIDATES'],2)
        script.RESULT.clear(); script.RESULT.update(script.INITIAL_RESULT)
        code,_=self.choose([],[])
        self.assertEqual(code,1)
        self.assertEqual(script.RESULT['EXIT_REASON'],'NO_ELIGIBLE_CANDIDATES')

    def test_cancel_or_unrecognized_input_never_selects_or_echoes_input(self):
        for answer in ['CANCEL','private-value-do-not-print','']:
            script.RESULT.clear(); script.RESULT.update(script.INITIAL_RESULT)
            code,output=self.choose([(1,0)],[answer])
            self.assertEqual(code,1)
            self.assertEqual(script.RESULT['EXIT_REASON'],'OPERATOR_CANCELLED')
            self.assertEqual(script.RESULT['ELIGIBLE_BUSINESS_FOUND'],'no')
            self.assertNotIn('private-value',output+str(script.RESULT))

    def run_mocked(self,action):
        with tempfile.TemporaryDirectory() as directory:
            report=Path(directory)/'synthetic-result.json'
            output=io.StringIO()
            with patch.object(script,'REPORT',report),patch.object(script,'main',side_effect=action),redirect_stdout(output):
                code=script.run()
            return code,output.getvalue(),json.loads(report.read_text())

    def test_console_and_saved_exhaustion_result_match(self):
        def action():
            with patch('builtins.input',return_value='SKIP'):
                return script.choose_candidate([(1,0)])
        code,output,saved=self.run_mocked(action)
        self.assertEqual(code,1)
        self.assertEqual(saved['EXIT_REASON'],'ALL_CANDIDATES_EXHAUSTED')
        for key,value in saved.items(): self.assertIn(key+'='+str(value),output)

    def test_eof_and_interrupt_are_saved_as_operator_cancellation(self):
        for exception in [EOFError(),KeyboardInterrupt()]:
            code,output,saved=self.run_mocked(exception)
            self.assertEqual(code,1)
            self.assertEqual(saved['EXIT_REASON'],'OPERATOR_CANCELLED')
            self.assertEqual(saved['ELIGIBLE_BUSINESS_FOUND'],'no')

    def test_database_or_authorization_error_is_safe_and_distinct(self):
        def fail():
            script.PHASE='DATABASE_INSPECTION'
            raise RuntimeError('private-password-and-record-content')
        code,output,saved=self.run_mocked(fail)
        self.assertEqual(code,1)
        self.assertEqual(saved['EXIT_REASON'],'DATABASE_OR_AUTHORIZATION_FAILURE')
        self.assertNotIn('private-password',output+str(saved))
        code,_,saved=self.run_mocked(RuntimeError('precheck'))
        self.assertEqual(saved['EXIT_REASON'],'LOCAL_OR_PRECHECK_FAILURE')

    def test_existing_evidence_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            report=Path(directory)/'prior.json'; report.write_text('preserve-existing-evidence')
            with patch.object(script,'REPORT',report),patch.object(script,'main',return_value=1),redirect_stdout(io.StringIO()):
                script.run()
            self.assertEqual(report.read_text(),'preserve-existing-evidence')


if __name__=='__main__': main(verbosity=2)
