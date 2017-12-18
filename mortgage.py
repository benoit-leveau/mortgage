#!/usr/bin/python

import re
import time
import tempfile
import urllib
from lxml.html import parse
from optparse import OptionParser, OptionGroup

MORTGAGE_TYPES=["FIRST_TIME_BUYER", "REMORTGAGE"]
PRODUCT_TYPES=["FIXED"]
SORT_BY=["MSETrueCost"]

def reportfunc(current, blocksize, filesize):
    pass

def parse_url(url, verbose=False):
    tmp_file = tempfile.mktemp()
    time.sleep(1)
    urllib.urlretrieve(url, filename=tmp_file, reporthook=reportfunc)
    time.sleep(1)
    if verbose:
        print "URL:", url
        print "TMP:", tmp_file
    doc = parse(tmp_file).getroot()
    return doc

def get_text(div):
    text = ""
    for line in div.text_content().split("\n"):
        line = line.strip()
        if line != "":
            text += " %s" % line
    return text

def construct_url(mortgage_type, borrowed, property_price, years, product_type, sort_by):
    url = "https://www.moneysavingexpert.com/mortgages/best-buys/?page=results&pageNumber=1&mortgagetype=%s&amountborrow=%d&propertyworth=%d&repayyears=%d&producttype%%5B%%5D=%s&banks_filter=&providerFilter%%5Bbank%%5D%%5B%%5D=-1&building_societies_filter=&providerFilter%%5Bbuilding_societies%%5D%%5B%%5D=-1&productlength%%5B%%5D=1&productlength%%5B%%5D=2&productlength%%5B%%5D=3&productlength%%5B%%5D=4&productlength%%5B%%5D=5&productlength%%5B%%5D=10&productlength%%5B%%5D=-1&resultsOrder=%s" % (mortgage_type, borrowed, property_price, years, product_type, sort_by)
    return url

def display(str):
    return " ".join(map(lambda x:x.capitalize(), str.lower().split("_")))


class Mortgage(object):
    def __init__(self, mortgage_type, borrowed, property_price, years, product_type, sort_by):
        self.mortgage_type = mortgage_type
        self.borrowed = borrowed
        self.property_price = property_price
        self.years = years
        self.product_type = product_type
        self.sort_by = sort_by
        self.offers = []

    def parse_offers(self, doc, years):
        result_divs = doc.body.find_class("result-wrap")
        self.offers = []
        for result_div in result_divs:
            text = get_text(result_div)
            m = re.search("Rate ([0-9]+\.[0-9]+)%", text)
            rate = 0
            monthly = 0
            fees = 0
            initial_duration = 0
            if m:
                rate = float(m.groups()[0])
            m = re.search("Set-up Fees: \xa3([0-9,]+)", text)
            if m:
                fees = float(m.groups()[0].replace(",", ""))
            m = re.search("Monthly Payment \xa3([0-9,]+)", text)
            if m:
                monthly = float(m.groups()[0].replace(",", ""))
            m = re.search("For ([0-9]+) months, then SVR", text)
            if m:
                initial_duration = int(m.groups()[0].replace(",", ""))
            offer = {"rate":rate,
                     "initial_duration":initial_duration,
                     "monthly":monthly,
                     "fees":fees,
                     "duration":years}
            self.offers.append(offer)
        return len(self.offers)
        
    def get(self):
        url = construct_url(self.mortgage_type, self.borrowed, self.property_price, self.years, self.product_type, self.sort_by)
        doc = parse_url(url, verbose=True)
        result = self.parse_offers(doc, self.years)
        if not result:
            retries = 0
            while retries<3:
                print "-- RETRYING --"
                time.sleep(5)
                doc = parse_url(url, verbose=True)
                result = self.parse_offers(doc, self.years)
                if result:
                    break
                retries += 1

    def display(self, limit=None):
        print "Mortgage Type: %s" % display(self.mortgage_type)
        print "Amount borrowed: %d" % self.borrowed
        print "Property value: %d" % self.property_price
        print "Duration: %d years" % self.years
        print "Product Type: %s" % display(self.product_type)
        for offer in self.offers[:limit if limit else len(a)]:
            print "-" * 20
            #print "Bank: %s" % offer["bank"]
            print "Rate: %s" % offer["rate"]
            print "Setup Fees: %s" % offer["fees"]
            print "Initial Deal: %s months" % offer["initial_duration"]
            print "Monthly Payment: %s" % offer["monthly"]
            print "Duration: %s years" % offer["duration"]
        print "-" * 20

def run_loop(deposit, property_price, max_monthly, apports):
    left_to_pay = property_price - deposit
    total_repaid = 0
    index = 0
    total_cost = 0
    total_duration = 0
    mortgages = []
    total_extra = 0
    while left_to_pay > 5000:
        # find best deal
        years = 30
        mortgage_type = "FIRST_TIME_BUYER" if index == 0 else "REMORTGAGE"
        product_type = PRODUCT_TYPES[0] # fixed
        sort_by = SORT_BY[0] # lowest cost
        best_offer = None
        for years in range(30,0,-1):
            if years > ((left_to_pay*2.0)/(max_monthly*12)):
                # we don't need to look for deals that are obviously too long
                continue
            if years < (left_to_pay/(max_monthly*12.0)):
                # we can't have a mortgage shorter than what it would take to repay
                # without fees
                break
            print "Looking for %s %s mortgage %d/%d over %d years..." % (mortgage_type, product_type, left_to_pay, property_price, years)
            mortgage = Mortgage(mortgage_type, left_to_pay, property_price, years, product_type, sort_by)
            mortgage.get()
            print "Found %d offers" % len(mortgage.offers)
            for offer in mortgage.offers:
                if offer["monthly"] > max_monthly:
                    continue
                if best_offer is None or offer["duration"] < best_offer["duration"]:
                    best_offer = offer
        if best_offer is None:
            print "Didn't find any offer"
            break
        mortgages.append(best_offer)
        print "Best offer found: %f%% - %dP fees - %dP/month - fixed %d months - %d years" % (best_offer["rate"], best_offer["fees"], best_offer["monthly"], best_offer["initial_duration"], best_offer["duration"])
        total_cost += best_offer["fees"]
        borrowing_value = left_to_pay
        for month in range(best_offer["initial_duration"]):
            if (month % 12) == 0:
                borrowing_value = left_to_pay
            month_payment = min(best_offer["monthly"], left_to_pay)
            total_cost += month_payment
            interest = (borrowing_value*best_offer["rate"]/100.0)/12.0
            repaid = month_payment-interest
            total_repaid += repaid
            total_duration += 1
            left_to_pay -= repaid
            print "- Month #%d - Pay %d (Interest %d - Repaid %d)" % (month+1, month_payment, interest, repaid)
            if (month == years*12):
                break
            if left_to_pay == 0:
                break
        print "-" * 40
        print "Mortgage #%d" % (index+1)
        print "Left to repay: %d" % left_to_pay
        print "Repaid so far: %d" % total_repaid
        print "Total Cost: %d" % total_cost
        print "Total Duration: %d years %d months" % (total_duration/12, total_duration%12)
        for (apport_amount, apport_date) in apports:
            if total_duration>apport_date:
                print '#' * 20
                print "# APPORT %d" % apport_amount
                print "To repay: %d => %d" % (left_to_pay, left_to_pay-apport_amount)
                print '#' * 20
                time.sleep(5)
                total_extra += apport_amount
                total_repaid += apport_amount
                left_to_pay -= apport_amount
                apports.remove((apport_amount, apport_date))
                break
        index += 1
    print ""
    print "#" * 40
    print "Summary"
    print ""
    print "Property:", property_price
    print "Deposit:", deposit
    print "Extra:", total_extra
    print "Total Duration: %d years %d months" % (total_duration/12, total_duration%12)
    print "Left to pay:", left_to_pay
    print "%d mortgages" % index
    for index, mortgage in enumerate(mortgages):
        print "- Mortage #%d: %f%% - %dP fees - %dP/month - fixed %d months - %d years" % (index+1, mortgage["rate"], mortgage["fees"], mortgage["monthly"], mortgage["initial_duration"], mortgage["duration"])
    print ""
    print "Total cost: %d" % (total_cost+deposit+total_extra)
    print "Total repaid: %d" % (total_repaid+deposit)
    print "Total fees & interest: %d" % (total_cost+total_extra-total_repaid)

def main():
    usage = "usage: %%prog [options]"
    parser = OptionParser(usage)

    group = OptionGroup(parser, "Action")
    group.add_option("--compare", action="store_true")
    group.add_option("--simulation", action="store_true")
    parser.add_option_group(group)

    parser.add_option("--property-value", type="int", help="Property value (default: %default)", default=100000)
    
    group = OptionGroup(parser, "Comparator")
    group.add_option("--limit", type="int", help="Limit to X entries (default: no limit)", default=None)
    group.add_option("--remortgage", action="store_true")
    group.add_option("--borrowed", type="int", help="Borrowed amount (default: %default)", default=90000)
    group.add_option("--years", type="int", help="Duration in years (default: %default)", default=25)
    parser.add_option_group(group)

    group = OptionGroup(parser, "Simulation")
    group.add_option("--deposit", type="int", help="Deposit (default: %default)", default=10000)
    group.add_option("--extra", type="str", action="append", help="Inject amount at specific dates (after initial duration expired) (amount, date_in_month)", default=None)
    group.add_option("--max-monthly", type="int", help="Max budget for monthly payments (default: %default)", default=1000)
    parser.add_option_group(group)
    
    # parse the command line
    (options, args) = parser.parse_args()

    if options.compare:
        if options.remortgage:
            mortgage_type = MORTGAGE_TYPES[1]
        else:
            mortgage_type = MORTGAGE_TYPES[0]        
        product_type = PRODUCT_TYPES[0]
        sort_by = SORT_BY[0]
        mortgage = Mortgage(mortgage_type, options.borrowed, options.property_value, options.years, product_type, sort_by)
        mortgage.get()
        mortgage.display(options.limit)
    elif options.simulation:
        apports = []
        for entry in options.extra:
            apports.append((int(entry.split(",")[0]), int(entry.split(",")[1])))
        run_loop(options.deposit, options.property_value, options.max_monthly, apports)
    

if __name__ == "__main__":
    main()
