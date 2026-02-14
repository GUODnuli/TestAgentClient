package com.bank.loan.mapper;

import com.bank.loan.model.LoanRequest;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface LoanMapper {

    int insertApplication(LoanRequest request);

    LoanRequest selectById(@Param("id") String id);

    int updateStatus(@Param("id") String id, @Param("status") String status);
}
