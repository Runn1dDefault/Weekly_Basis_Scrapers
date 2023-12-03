import os

import scrapy
from scrapy import Selector
from scrapy.loader import ItemLoader

from ecommerce.items import Product
from ecommerce.settings import SCREEN_DIR


class JoueclubSpider(scrapy.Spider):
    name = 'joueclub'
    allowed_domains = ['www.joueclub.fr']
    start_urls = [
        'https://www.joueclub.fr/gravitrax-bloc-d-action-zipline-tyrolienne.html',
    ]
    custom_settings = {
        "DOWNLOAD_DELAY": 0.25,
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
    }

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                self.parse,
                meta={
                    'playwright': True,
                    "playwright_include_page": True
                }
            )

    async def parse(self, response, **kwargs):
        page = response.meta["playwright_page"]
        html = await page.content()
        sel = Selector(text=html)
        loader = ItemLoader(item=Product(), selector=sel)
        loader.add_value('link', response.url)
        list_li = sel.xpath('//ul[@class="list list-dash mt-0"]/li/text()').getall()
        sku = None
        for i in list_li:
            if 'Code barre :' in i:
                sku = i.replace('Code barre :', '').strip()
                break
        loader.add_value('ean', sku)
        loader.add_xpath('title', '//p[@class="c-product-header__title"]')
        loader.add_xpath('price', '//span[@class="c-product-price__price-value"]')
        loader.add_xpath('description', '//div[@data-ng-if="information.key === \'jcp_description\'"]')
        loader.add_xpath('breadcrumb', '//ul[@class="breadcrumb"]//span')
        screenshot_path = os.path.join(SCREEN_DIR, f'{self.name}_{sku}.png')
        await page.screenshot(path=screenshot_path, full_page=True)
        loader.add_value('screenshot', screenshot_path)
        await page.close()
        yield loader.load_item()
