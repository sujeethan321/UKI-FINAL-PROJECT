"""Bounded Groq-only transport. One attempt; no tools, redirects or retries."""
from __future__ import annotations
import asyncio
import json
import httpx
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.core.config import Settings
from app.integrations.ai.base import AIClientError,AIFailureCategory,GenerationRequest,GenerationResult,MAX_GENERATION_INPUT_BYTES
from app.integrations.ai.limits import budget

MAX_INPUT_BYTES=MAX_GENERATION_INPUT_BYTES
MODEL='openai/gpt-oss-120b'

def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate JSON field')
        result[key]=value
    return result

class GroqAIClient:
    def __init__(self,config:Settings,http_client:httpx.AsyncClient):
        self._config=config;self._http=http_client
        timeout=config.GROQ_TIMEOUT_SECONDS
        self._timeout=httpx.Timeout(timeout,connect=min(3.0,timeout),read=timeout,write=timeout,pool=min(3.0,timeout))

    def _credential(self):
        if not self._config.AI_ENABLED or self._config.GROQ_API_KEY is None or self._config.GROQ_MODEL!=MODEL or self._config.GROQ_BASE_URL!='https://api.groq.com/openai/v1':
            raise AIClientError(AIFailureCategory.CONFIGURATION)
        secret=self._config.GROQ_API_KEY.get_secret_value()
        if not secret.strip():raise AIClientError(AIFailureCategory.CONFIGURATION)
        return secret

    def _validate_request(self,request,credential):
        if not isinstance(request,GenerationRequest):raise AIClientError(AIFailureCategory.INVALID_REQUEST)
        prompts=(request.system_prompt,request.user_prompt)
        if any(not isinstance(p,str) or not p.strip() or '\x00' in p or credential in p for p in prompts):
            raise AIClientError(AIFailureCategory.INVALID_REQUEST)
        try:schema=json.dumps(request.response_schema,separators=(',',':')) if request.response_schema is not None else ''
        except (ValueError,TypeError):raise AIClientError(AIFailureCategory.INVALID_REQUEST) from None
        if sum(len(p.encode()) for p in prompts)+len(schema.encode())>MAX_INPUT_BYTES or credential in schema:
            raise AIClientError(AIFailureCategory.INVALID_REQUEST)

    @staticmethod
    def _result(payload,model,max_tokens):
        try:
            if payload.get('model',model)!=model:raise ValueError()
            choices=payload['choices']
            if not isinstance(choices,list) or len(choices)!=1:raise ValueError()
            choice=choices[0];message=choice['message'];content=message['content']
            if choice.get('finish_reason')!='stop' or message.get('tool_calls') or message.get('function_call') or message.get('refusal'):raise ValueError()
            if not isinstance(content,str) or not content.strip() or len(content.encode())>max_tokens*32:raise ValueError()
            used=payload.get('usage',{}).get('completion_tokens',0)
            if not isinstance(used,int) or isinstance(used,bool) or used<0 or used>max_tokens:raise ValueError()
        except (ValueError,KeyError,TypeError,AttributeError):
            raise AIClientError(AIFailureCategory.INVALID_RESPONSE) from None
        return GenerationResult(content.strip(),model,'stop')

    async def generate(self,request):
        credential=self._credential();self._validate_request(request,credential)
        body={'model':MODEL,'messages':[{'role':'system','content':request.system_prompt},{'role':'user','content':request.user_prompt}],
            'max_tokens':self._config.GROQ_MAX_OUTPUT_TOKENS,'temperature':0.2}
        if request.response_schema is not None:
            body['response_format']={'type':'json_schema','json_schema':{'name':'financial_explanation','strict':True,'schema':request.response_schema}}
        try:
            with budget.reserve(self._config):
                async with asyncio.timeout(float(self._config.GROQ_TIMEOUT_SECONDS)):
                    async with self._http.stream('POST',self._config.GROQ_BASE_URL+'/chat/completions',
                        headers={'Authorization':'Bearer '+credential,'Content-Type':'application/json','Accept-Encoding':'identity'},
                        json=body,timeout=self._timeout,follow_redirects=False) as response:
                        if response.status_code in (401,403):raise AIClientError(AIFailureCategory.AUTHENTICATION)
                        if response.status_code==429:raise AIClientError(AIFailureCategory.RATE_LIMITED)
                        if response.status_code>=500:raise AIClientError(AIFailureCategory.PROVIDER_ERROR)
                        if response.status_code!=200:raise AIClientError(AIFailureCategory.INVALID_REQUEST)
                        if response.headers.get('content-encoding','identity').lower()!='identity':raise AIClientError(AIFailureCategory.INVALID_RESPONSE)
                        maximum=getattr(self._config,'GROQ_MAX_RESPONSE_BYTES',65536)
                        declared=response.headers.get('content-length')
                        if declared is not None and (not declared.isdigit() or int(declared)>maximum):raise AIClientError(AIFailureCategory.INVALID_RESPONSE)
                        content=bytearray()
                        if response.is_stream_consumed:
                            if len(response.content)>maximum:raise AIClientError(AIFailureCategory.INVALID_RESPONSE)
                            content.extend(response.content)
                        else:
                            async for chunk in response.aiter_raw(chunk_size=4096):
                                if len(content)+len(chunk)>maximum:raise AIClientError(AIFailureCategory.INVALID_RESPONSE)
                                content.extend(chunk)
                        payload=json.loads(content,object_pairs_hook=unique_object)
                        return self._result(payload,MODEL,self._config.GROQ_MAX_OUTPUT_TOKENS)
        except (httpx.TimeoutException,TimeoutError):raise AIClientError(AIFailureCategory.TIMEOUT) from None
        except httpx.RequestError:raise AIClientError(AIFailureCategory.CONNECTION) from None
        except (ValueError,UnicodeError,RecursionError):raise AIClientError(AIFailureCategory.INVALID_RESPONSE) from None
        except AIClientError:raise
        except Exception:raise AIClientError(AIFailureCategory.PROVIDER_ERROR) from None
