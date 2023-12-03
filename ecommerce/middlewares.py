import base64
import logging

from cfscrape import get_tokens
from twisted.internet import reactor
from twisted.internet.defer import Deferred


class ProxyMiddleware(object):
    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings)

    def __init__(self, settings):
        self.user = settings.get('PROXY_USER', 'lum-auth-token')
        self.password = settings.get('PROXY_PASSWORD', 'BjwW5d4etXa5SbuNzDnWxTFvbAguDzc')
        self.endpoint = settings.get('PROXY_ENDPOINT', 'devops.data-ox.com')
        self.port = settings.get('PROXY_PORT', 24261)

    def process_request(self, request, spider):
        user_credentials = '{user}:{passw}'.format(user=self.user, passw=self.password)
        basic_authentication = 'Basic ' + base64.b64encode(user_credentials.encode()).decode()
        host = 'http://{endpoint}:{port}'.format(endpoint=self.endpoint, port=self.port)
        request.meta['proxy'] = host
        request.headers['Proxy-Authorization'] = basic_authentication


class DelayedRequestsMiddleware(object):
    def process_request(self, request, spider):
        delay_s = request.meta.get('delay_request_by', None)
        if not delay_s:
            return

        deferred = Deferred()
        reactor.callLater(delay_s, deferred.callback, None)
        return deferred


class CloudFlareMiddleware:
    """Scrapy middleware to bypass the CloudFlare's anti-bot protection"""

    @staticmethod
    def is_cloudflare_challenge(response):
        """Test if the given response contains the cloudflare's anti-bot protection"""

        return (
            response.status == 503
            and response.headers.get('Server', '').startswith(b'cloudflare')
            and 'jschl_vc' in response.text
            and 'jschl_answer' in response.text
        )

    def process_response(self, request, response, spider):
        """Handle the a Scrapy response"""

        if not self.is_cloudflare_challenge(response):
            return response

        logger = logging.getLogger('cloudflaremiddleware')

        logger.debug(
            'Cloudflare protection detected on %s, trying to bypass...',
            response.url
        )

        cloudflare_tokens, __ = get_tokens(
            request.url,
            user_agent=spider.settings.get('USER_AGENT')
        )

        logger.debug(
            'Successfully bypassed the protection for %s, re-scheduling the request',
            response.url
        )

        request.cookies.update(cloudflare_tokens)
        request.priority = 99999

        return request

