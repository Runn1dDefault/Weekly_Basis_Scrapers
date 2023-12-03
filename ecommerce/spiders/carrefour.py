import os
from datetime import datetime
from urllib.parse import urlparse

import scrapy
from scrapy import Selector
from scrapy.loader import ItemLoader
from scrapy_playwright.page import PageCoroutine

from ecommerce.items import Product
from ecommerce.settings import SCREEN_DIR


class СarreFourSpider(scrapy.Spider):
    name = 'carrefour'
    allowed_domains = ['www.carrefour.fr']
    start_urls = [
        'https://www.carrefour.fr/p/ketchup-heinz-0000087157215'
    ]
    custom_settings = {
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
    }

    def start_requests(self):
        for url in self.start_urls:
            gtin = urlparse(url).path.split('/')[-1].split('-')[-1]
            yield scrapy.Request(
                url, self.parse,
                meta={
                    'playwright': True,
                    "playwright_include_page": True,
                    "playwright_page_coroutines": {
                        "clickallbtns": PageCoroutine(
                            "evaluate",
                            "document.querySelector('#onetrust-accept-btn-handler').click()"
                        ),
                    },
                    'gtin': gtin
                },
                errback=self.errback
            )

    async def parse(self, response, **kwargs):
        page = response.meta["playwright_page"]
        gtin = response.meta['gtin']
        html = await page.content()
        sel = Selector(text=html)
        loader = ItemLoader(item=Product(), selector=sel)
        loader.add_value('link', response.url)
        loader.add_value('ean', gtin)
        loader.add_xpath('title', '//h1')
        loader.add_xpath('description', '//div[@class="secondary-details__description"]/p')
        loader.add_xpath('price', '//div[@class="product-card-price__price"]')
        loader.add_xpath('breadcrumb', '//*[@class="breadcrumb-trail__list"]/li')
        screenshot_path = os.path.join(SCREEN_DIR, f'{self.name}_{gtin}_{int(datetime.now().timestamp())}.png')
        await page.screenshot(path=screenshot_path, full_page=True)
        loader.add_value('screenshot', screenshot_path)
        # TODO: reviews not found
        await page.close()
        yield loader.load_item()

    async def errback(self, failure):
        page = failure.request.meta["playwright_page"]
        await page.close()
