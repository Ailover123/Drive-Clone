create database emp_details;
use emp_details;

CREATE TABLE Departments (
    id INT AUTO_INCREMENT PRIMARY KEY,         
    D_name VARCHAR(100) NOT NULL,                
    location VARCHAR(100)                      
);
CREATE TABLE Employees (
    id INT AUTO_INCREMENT PRIMARY KEY,         
    first_name VARCHAR(50) NOT NULL,           
    last_name VARCHAR(50) NOT NULL,            
    email VARCHAR(100) NOT NULL UNIQUE,        
    phone_number VARCHAR(20),                  
    hire_date DATE NOT NULL,                   
    job_title VARCHAR(50) NOT NULL,            
    department_id INT,                         
    FOREIGN KEY (department_id) REFERENCES Departments(id)
);
CREATE TABLE Projects (
    id INT AUTO_INCREMENT PRIMARY KEY,         
    P_name VARCHAR(100) NOT NULL,                
    P_Description TEXT,                          
    start_date DATE,                           
    end_date DATE,                             
    department_id INT,                        
    FOREIGN KEY (department_id) REFERENCES Departments(id) 
);

CREATE TABLE Timesheets (
    id INT AUTO_INCREMENT PRIMARY KEY,         
    employee_id INT,                           
    project_id INT,                            
    date_ts DATE NOT NULL,                        
    hours DECIMAL(5, 2) NOT NULL,              
    FOREIGN KEY (employee_id) REFERENCES Employees(id),   
    FOREIGN KEY (project_id) REFERENCES Projects(id)      
);

INSERT INTO Departments (D_name, location) VALUES
('HR', 'New York'),           
('Finance', 'Chicago'),       
('Engineering', 'San Francisco'), 
('Marketing', 'Los Angeles'), 
('Sales', 'Boston'),
('IT Support', 'San Diego'), 
('Legal', 'Seattle'),        
('Operations', 'Houston'),   
('Customer Service','Miami');

INSERT INTO Employees (first_name, last_name, email, phone_number, hire_date, job_title, department_id) VALUES
('John', 'Doe', 'john.doe@example.com', '555-1234', '2022-01-15', 'Manager',1),
('Jane', 'Smith', 'jane.smith@example.com', '555-2345', '2021-06-22', 'Developer',3),
('Tom', 'Brown', 'tom.brown@example.com', '555-3456', '2020-09-12', 'Manager',2),
('Lucy', 'Davis', 'lucy.davis@example.com', '555-4567', '2019-11-02', 'Developer',4),
('Mark', 'Taylor', 'mark.taylor@example.com', '555-5678', '2018-08-30', 'Sales Rep',5),
('Emma', 'Watson', 'emma.watson@example.com', '555-8765', '2020-05-14', 'Manager',6),
('David', 'Miller', 'david.miller@example.com', '555-7654', '2019-04-20', 'Developer',6),
('Sophia', 'Wilson', 'sophia.wilson@example.com', '555-6543', '2018-12-01', 'Manager',7),
('Liam', 'Johnson', 'liam.johnson@example.com', '555-5432', '2021-07-17', 'Developer',7),
('Olivia', 'Martinez', 'olivia.martinez@example.com', '555-4321', '2022-09-09', 'HR Specialist',1),
('Lucas', 'Garcia', 'lucas.garcia@example.com', '555-3210', '2023-02-22', 'Marketing Analyst',4),
('Mia', 'Davis', 'mia.davis@example.com', '555-2109', '2023-03-15', 'Sales Rep',5),
('James', 'Brown', 'james.brown@example.com', '555-1098', '2021-10-11', 'Operations Manager',8),
('Isabella', 'Rodriguez', 'isabella.rodriguez@example.com', '555-0987', '2017-08-06', 'Customer Service Rep',9);

INSERT INTO Projects (P_name, P_Description, start_date, end_date, department_id) VALUES
('Project A', 'HR system overhaul', '2023-01-01', '2023-12-31',1),
('Project B', 'Financial Audit', '2023-03-01', '2023-12-01',2),
('Project C', 'New App Development', '2023-05-01', '2024-01-31',3),
('Project D', 'Marketing Campaign', '2023-07-01', '2023-11-30',4),
('Project E', 'Sales Platform Upgrade', '2023-09-01', '2024-06-30',5),
('Project F', 'IT Infrastructure Upgrade', '2023-04-01', '2023-12-31',6),
('Project G', 'Legal Compliance Audit', '2023-07-01', '2023-12-01',7),
('Project H', 'Operations Workflow Optimization', '2023-05-15', '2023-12-31',8),
('Project I', 'Customer Feedback System', '2023-06-01', '2024-03-31',9),
('Project J', 'Cloud Migration', '2023-09-01', '2024-05-31',6);

INSERT INTO Timesheets (employee_id, project_id, date_ts, hours) VALUES
(1, 1, '2023-02-15',8.0),
(2, 3, '2023-05-10',6.5),
(2, 3, '2023-05-11',7.0),
(3, 2, '2023-03-20',8.0),
(4, 4, '2023-08-10',5.5),
(4, 4, '2023-08-11',7.5),
(5, 5, '2023-10-15',6.0),
(6, 6, '2023-06-15',7.5), 
(7, 6, '2023-06-16',8.0), 
(7, 6, '2023-06-17',6.5),
(8, 7, '2023-08-01',8.0), 
(9, 7, '2023-08-02',7.0), 
(9, 7, '2023-08-03',8.5),
(10, 1, '2023-04-01',8.0), 
(11, 4, '2023-05-22',6.0), 
(11, 4, '2023-05-23',5.5),
(12, 5, '2023-09-15',7.0), 
(13, 8, '2023-07-05',6.5), 
(13, 8, '2023-07-06',8.0),
(14, 9, '2023-07-10',6.0), 
(14, 9, '2023-07-11',6.5),
(1, 3, '2023-06-12',7.5), 
(1, 3, '2023-06-13',8.0),
(2, 3, '2023-06-14',7.0);