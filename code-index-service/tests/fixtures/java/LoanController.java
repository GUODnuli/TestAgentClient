package com.bank.loan.controller;

import com.bank.loan.service.LoanService;
import com.bank.loan.model.LoanRequest;
import com.bank.loan.model.Response;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/loan")
public class LoanController {

    private LoanService loanService;

    @TransCode(value = "LN_LOAN_APPLY", name = "Loan Application")
    @PostMapping("/apply")
    public Response apply(@RequestBody LoanRequest request) {
        return loanService.submitApplication(request);
    }

    @GetMapping("/status/{id}")
    public Response getStatus(@PathVariable String id) {
        return loanService.queryStatus(id);
    }
}
