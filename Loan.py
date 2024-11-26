import pandas as pd
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from calendar import monthrange
from collections import OrderedDict
from typing import Optional
import pandas as pd
class Loan:
    def __init__(self, loan_amount: float, rate: float, fund_date: date, maturity_date: date, payment_type: str, interest_only_periods: Optional[int]=0, amortizing_periods: Optional[int]=360 ):
        if loan_amount <= 0:
            raise ValueError("Loan amount must be positive.")
        if rate < 0 or rate > 1:
            raise ValueError("Rate must be between 0 and 1.")
        if fund_date >= maturity_date:
            raise ValueError("Funding date must precede maturity date.")
        if payment_type not in ['Actual/360', '30/360', 'Actual/365']:
            raise ValueError(f"Unsupported payment type: {payment_type}")
        self.loan_amount = loan_amount
        self.rate = rate
        self.fund_date = self.get_end_of_month(fund_date)
        self.maturity_date = self.get_end_of_month(maturity_date)
        self.payment_type = payment_type
        self.interest_only_periods = interest_only_periods
        self.amortizing_periods = amortizing_periods
        self.amortizing_payment = self.calculate_amortizing_payment(loan_amount)
        self.schedule = self.initialize_loan_schedule()
        self.loan_draws = self.initialize_monthly_activity()
        self.loan_paydowns = self.initialize_monthly_activity()

    def get_end_of_month(self, input_date: date) -> date:
        """Set the date to the last day of its month."""
        last_day = monthrange(input_date.year, input_date.month)[1]  # Get the last day of the month
        return date(input_date.year, input_date.month, last_day)

    def get_prior_month(self, input_date: date) -> date:
        """Returns the last day of the prior month."""
        prior_month = input_date - relativedelta(months=1)
        return prior_month.replace(day=1) + relativedelta(day=31)

    def calculate_interest(self, balance: float, start_date: date, end_date: date) -> float:
        date_delta = (end_date - start_date).days
        payment_type_numerators = {'Actual/360': date_delta, '30/360': 30, 'Actual/365': date_delta}
        payment_type_denominators = {'Actual/360': 360, '30/360': 360, 'Actual/365': 365}
        payment_type_numerator = payment_type_numerators[self.payment_type]
        payment_type_denominator = payment_type_denominators[self.payment_type]
        return balance * self.rate * payment_type_numerator / payment_type_denominator

    def calculate_amortizing_payment(self, loan_balance):
        if self.amortizing_periods == 0:
            return 0
        # Convert annual rate to monthly rate)
        monthly_rate = self.rate / 12
        # Total number of payments
        total_payments = self.amortizing_periods

        # Amortizing payment formula
        if monthly_rate == 0:  # Handle zero-interest loans
            return loan_balance / total_payments
        else:
            return loan_balance * (monthly_rate * (1 + monthly_rate) ** total_payments) / (
                        (1 + monthly_rate) ** total_payments - 1)

    def initialize_monthly_activity(self) -> OrderedDict:
        return OrderedDict({
            month:0 for month in self.monthly_dates
        })

    def add_loan_draw(self, draw: float, draw_date: date):
        self.loan_draws[draw_date] = draw
        self.generate_loan_schedule()
        return

    def add_loan_paydown(self, paydown: float, paydown_date: date):
        self.loan_paydowns[paydown_date] = paydown
        self.generate_loan_schedule()
        return

    def get_loan_draw(self, draw_date: date):
        return self.loan_draws[draw_date]

    def get_loan_paydown(self, paydown_date: date):
        return self.loan_paydowns[paydown_date]

    def initialize_loan_schedule(self) -> OrderedDict:
        """Initialize the loan schedule as an ordered dictionary."""
        self.monthly_dates = [
            self.get_end_of_month(self.fund_date + relativedelta(months=i))
            for i in range(
                (self.maturity_date.year - self.fund_date.year) * 12 +
                self.maturity_date.month - self.fund_date.month + 1
            )
        ]
        return OrderedDict({
            month: {
                'beginning_balance': 0,
                'loan_draw': 0,
                'loan_paydown': 0,
                'interest_payment': 0,
                'scheduled_principal_payment': 0,
                'ending_balance': 0
            } for month in self.monthly_dates
        })

    def get_scheduled_principal_payment(self, period, amortizing_payment, interest_payment):
        if period <= self.interest_only_periods:
            return 0
        return amortizing_payment - interest_payment
    def generate_loan_schedule(self) -> OrderedDict:
        """Populate the loan schedule with initial values."""
        i = 0
        prior_key = self.fund_date
        for key in list(self.schedule.keys()):
            if i==0:
                self.schedule[key]['beginning_balance'] = 0
                self.schedule[key]['loan_draw'] = self.loan_amount
                self.schedule[key]['ending_balance'] = self.loan_amount
            else:
                self.schedule[key]['beginning_balance'] = self.schedule[prior_key]['ending_balance']
                amortizing_payment = self.calculate_amortizing_payment(self.schedule[key]['beginning_balance'])
                self.schedule[key]['loan_draw'] = self.get_loan_draw(key)
                self.schedule[key]['interest_payment'] = self.calculate_interest(
                    self.schedule[key]['beginning_balance'],
                    prior_key,
                    key
                )
                if self.amortizing_periods == 0:
                    self.schedule[key]['scheduled_principal_payment'] = 0
                else:
                    self.schedule[key]['scheduled_principal_payment'] = self.amortizing_payment - self.schedule[key]['interest_payment']
                if key == self.maturity_date:
                    self.schedule[key]['loan_paydown'] = self.schedule[key]['beginning_balance'] - self.schedule[key]['scheduled_principal_payment']
                else:
                    self.schedule[key]['loan_paydown'] = self.get_loan_paydown(key)
                self.schedule[key]['ending_balance'] = self.schedule[key]['beginning_balance'] + self.schedule[key]['loan_draw'] - self.schedule[key]['loan_paydown'] - self.schedule[key]['scheduled_principal_payment']

                prior_key = key
            i += 1

        return self.schedule


# Example usage
loan = Loan(
    loan_amount=1000000,
    rate=0.05,
    fund_date=date(2024, 11, 1),
    maturity_date=date(2054, 11, 30),
    interest_only_periods=0,
    amortizing_periods=0,
    payment_type='30/360'
)

#loan.add_loan_draw(500000,date(2025,2,28),)
#loan.add_loan_draw(500000,date(2025,5,31),)
#loan.add_loan_paydown(250000,date(2025,9,30),)

df = pd.DataFrame.from_dict(loan.generate_loan_schedule()).T
df.to_excel("/users/scottdunphy/downloads/loan.xlsx")
