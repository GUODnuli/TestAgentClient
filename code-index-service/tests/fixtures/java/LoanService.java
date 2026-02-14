package com.bank.loan.service;

import com.bank.loan.mapper.LoanMapper;
import com.bank.loan.model.LoanRequest;
import com.bank.loan.model.Response;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class LoanService {

    private LoanMapper loanMapper;

    @Transactional
    public Response submitApplication(LoanRequest request) {
        // Validate input
        if (request.getAmount() == null || request.getAmount() <= 0) {
            throw new IllegalArgumentException("Invalid amount");
        }

        // Check amount threshold
        if (request.getAmount() > 1000000) {
            // Requires risk control approval
            request.setStatus("PENDING_REVIEW");
        } else {
            // Auto approval
            request.setStatus("AUTO_APPROVED");
        }

        // Save to database
        loanMapper.insertApplication(request);

        return Response.success(request);
    }

    public Response queryStatus(String id) {
        return Response.success(loanMapper.selectById(id));
    }
}
